"""Hesap akislari: kayit, dogrulama, giris, oturum, parola ve yonetici uclari.

Gercek SQL (SQLite dosyasi) ve bellek ici sahte Redis ile uctan uca calisir.
"""

import re
from datetime import UTC, datetime

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.auth import security
from app.core import config
from app.core.db import Base, get_db
from app.main import app
from app.models import AppUser, InviteCode, UserSession, UserToken, UserWatchlistItem

SERVICE = {"X-Admin-Token": "test-service-token"}
PASSWORD = "dogru-parola-123"
# Sabit dizeden turetilir; gitleaks genel anahtar kuralina takilmasin.
NEW_PASSWORD = f"{PASSWORD}-yeni"
TABLES = [
    InviteCode.__table__,
    AppUser.__table__,
    UserSession.__table__,
    UserToken.__table__,
    UserWatchlistItem.__table__,
]


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    async def get(self, key: str):
        return self.values.get(key)

    async def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key: str, seconds: int) -> None:
        return None


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / "auth.db"
    sync_engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(sync_engine, tables=TABLES)
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}", poolclass=NullPool)

    @event.listens_for(engine.sync_engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(config.get_settings(), "admin_api_token", SERVICE["X-Admin-Token"])
    monkeypatch.setattr("app.auth.ratelimit.get_redis", lambda: FakeRedis.instance)
    FakeRedis.instance = FakeRedis()
    # Testlerde ucuz ozet; davranis ayni (argon2id).
    monkeypatch.setattr(
        security, "_hasher", PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    )

    mode = {"value": "invite"}

    async def fake_resolve_settings():
        return config.get_settings().model_copy(update={"registration_mode": mode["value"]})

    monkeypatch.setattr("app.auth.service.resolve_settings", fake_resolve_settings)

    mails: list = []

    async def capture(mail):
        mails.append(mail)
        return True

    monkeypatch.setattr("app.api.routers.auth.enqueue_mail", capture)
    monkeypatch.setattr("app.api.routers.me.enqueue_mail", capture)

    with TestClient(app) as client:
        yield {"client": client, "db": sync_engine, "mails": mails, "mode": mode}
    app.dependency_overrides.pop(get_db, None)
    sync_engine.dispose()


def _invite(env, code="ABCD-EFGH-JKLM", max_uses=1) -> str:
    with Session(env["db"]) as session:
        session.add(InviteCode(code=code, note="", max_uses=max_uses, used_count=0))
        session.commit()
    return code


def _token_from(mail) -> str:
    return re.search(r"token=([\w\-]+)", mail.text).group(1)


def _register(env, email="ayse@example.com", invite="", password=PASSWORD):
    return env["client"].post(
        "/api/auth/register",
        headers=SERVICE,
        json={
            "email": email,
            "password": password,
            "display_name": "Ayşe",
            "invite_code": invite,
            "accept_terms": True,
            "client_ip": "10.0.0.1",
        },
    )


def _login(env, email="ayse@example.com", password=PASSWORD, ip="10.0.0.1"):
    return env["client"].post(
        "/api/auth/login",
        headers=SERVICE,
        json={"email": email, "password": password, "client_ip": ip, "user_agent": "pytest"},
    )


def _verified_user(env, email="ayse@example.com") -> str:
    """Kayit + dogrulama + giris; oturum token'ini dondurur."""
    env["mode"]["value"] = "open"
    assert _register(env, email=email).status_code == 202
    token = _token_from(env["mails"][-1])
    assert (
        env["client"]
        .post("/api/auth/verify-email", headers=SERVICE, json={"token": token})
        .status_code
        == 200
    )
    response = _login(env, email=email)
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_auth_endpoints_require_service_token(env):
    assert env["client"].get("/api/auth/config").status_code == 401
    assert env["client"].get("/api/auth/config", headers=SERVICE).json()["registration_mode"] == (
        "invite"
    )


def test_invite_mode_requires_valid_invite_and_consumes_it_once(env):
    response = _register(env, invite="YANLIS-KOD")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_invite"

    code = _invite(env)
    assert _register(env, invite=code.lower()).status_code == 202
    assert env["mails"][-1].subject.endswith("E-posta adresini doğrula")
    with Session(env["db"]) as session:
        assert session.scalar(select(InviteCode.used_count)) == 1
        user = session.scalar(select(AppUser))
        assert user.email == "ayse@example.com"
        assert user.terms_version and user.invite_code_id is not None
        assert user.password_hash.startswith("$argon2id$")

    assert _register(env, email="baska@example.com", invite=code).status_code == 422


def test_registering_existing_email_looks_identical_and_keeps_invite(env):
    env["mode"]["value"] = "open"
    first = _register(env)
    env["mode"]["value"] = "invite"
    code = _invite(env)
    second = _register(env, email="  AYSE@example.com ", invite=code)

    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    assert env["mails"][-1].subject.endswith("zaten bir hesabın var")
    with Session(env["db"]) as session:
        assert session.scalar(select(InviteCode.used_count)) == 0
        assert len(session.scalars(select(AppUser)).all()) == 1


def test_closed_mode_and_validation_errors(env):
    env["mode"]["value"] = "closed"
    assert _register(env).json()["detail"]["code"] == "registration_closed"
    env["mode"]["value"] = "open"
    assert _register(env, password="kisa").json()["detail"]["code"] == "weak_password"
    assert _register(env, email="gecersiz").json()["detail"]["code"] == "invalid_email"
    response = env["client"].post(
        "/api/auth/register",
        headers=SERVICE,
        json={"email": "a@example.com", "password": PASSWORD, "accept_terms": False},
    )
    assert response.json()["detail"]["code"] == "terms_required"


def test_login_requires_verified_email_and_hides_state_on_wrong_password(env):
    env["mode"]["value"] = "open"
    _register(env)
    assert _login(env, password="yanlis-parola-1").status_code == 401
    unverified = _login(env)
    assert unverified.status_code == 403
    assert unverified.json()["detail"]["code"] == "email_not_verified"

    token = _token_from(env["mails"][-1])
    verify = env["client"].post("/api/auth/verify-email", headers=SERVICE, json={"token": token})
    assert verify.status_code == 200
    again = env["client"].post("/api/auth/verify-email", headers=SERVICE, json={"token": token})
    assert again.json()["detail"]["code"] == "invalid_token"

    login = _login(env)
    assert login.status_code == 200
    body = login.json()
    assert body["user"]["email_verified"] is True and body["user"]["role"] == "user"
    with Session(env["db"]) as session:
        stored = session.scalar(select(UserSession.token_hash))
    assert stored == security.hash_token(body["token"]) != body["token"]


def test_me_requires_valid_bearer_token(env):
    token = _verified_user(env)
    client = env["client"]
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers=_bearer("uydurma")).status_code == 401
    me = client.get("/api/me", headers=_bearer(token))
    assert me.status_code == 200 and me.json()["display_name"] == "Ayşe"

    patched = client.patch("/api/me", headers=_bearer(token), json={"display_name": "Ayşe K."})
    assert patched.json()["display_name"] == "Ayşe K."

    assert client.post("/api/me/logout", headers=_bearer(token)).status_code == 204
    assert client.get("/api/me", headers=_bearer(token)).status_code == 401


def test_expired_session_is_rejected(env):
    token = _verified_user(env)
    with Session(env["db"]) as session:
        session.execute(update(UserSession).values(expires_at=datetime(2020, 1, 1, tzinfo=UTC)))
        session.commit()
    assert env["client"].get("/api/me", headers=_bearer(token)).status_code == 401


def test_watchlists_are_isolated_per_user(env):
    ayse = _verified_user(env, "ayse@example.com")
    mehmet = _verified_user(env, "mehmet@example.com")
    client = env["client"]

    saved = client.put(
        "/api/me/watchlist", headers=_bearer(ayse), json={"tickers": ["thyao", "ASELS", "THYAO"]}
    )
    assert saved.json()["tickers"] == ["ASELS", "THYAO"]
    assert client.get("/api/me/watchlist", headers=_bearer(mehmet)).json()["tickers"] == []

    client.put("/api/me/watchlist", headers=_bearer(mehmet), json={"tickers": ["GARAN"]})
    replaced = client.put("/api/me/watchlist", headers=_bearer(ayse), json={"tickers": ["ASELS"]})
    assert replaced.json()["tickers"] == ["ASELS"]
    assert client.get("/api/me/watchlist", headers=_bearer(mehmet)).json()["tickers"] == ["GARAN"]


def test_password_change_revokes_other_sessions(env):
    first = _verified_user(env)
    second = _login(env).json()["token"]
    client = env["client"]

    sessions = client.get("/api/me/sessions", headers=_bearer(first)).json()
    assert len(sessions) == 2 and sum(item["current"] for item in sessions) == 1

    wrong = client.post(
        "/api/me/password",
        headers=_bearer(first),
        json={"current_password": "yanlis-parola-1", "new_password": NEW_PASSWORD},
    )
    assert wrong.status_code == 400
    changed = client.post(
        "/api/me/password",
        headers=_bearer(first),
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert changed.status_code == 200
    assert env["mails"][-1].subject.endswith("Parolan değiştirildi")
    assert client.get("/api/me", headers=_bearer(first)).status_code == 200
    assert client.get("/api/me", headers=_bearer(second)).status_code == 401
    assert _login(env, password=NEW_PASSWORD).status_code == 200


def test_password_reset_flow_and_no_account_enumeration(env):
    old_session = _verified_user(env)
    client = env["client"]
    mail_count = len(env["mails"])

    unknown = client.post(
        "/api/auth/password-reset/request", headers=SERVICE, json={"email": "yok@example.com"}
    )
    known = client.post(
        "/api/auth/password-reset/request", headers=SERVICE, json={"email": "ayse@example.com"}
    )
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    assert len(env["mails"]) == mail_count + 1
    token = _token_from(env["mails"][-1])

    weak = client.post(
        "/api/auth/password-reset/confirm",
        headers=SERVICE,
        json={"token": token, "password": "kisa"},
    )
    assert weak.status_code == 422
    done = client.post(
        "/api/auth/password-reset/confirm",
        headers=SERVICE,
        json={"token": token, "password": "sifirlanan-parola-9"},
    )
    assert done.status_code == 200
    assert client.get("/api/me", headers=_bearer(old_session)).status_code == 401
    assert _login(env, password=PASSWORD).status_code == 401
    assert _login(env, password="sifirlanan-parola-9").status_code == 200
    reused = client.post(
        "/api/auth/password-reset/confirm",
        headers=SERVICE,
        json={"token": token, "password": "baska-parola-77"},
    )
    assert reused.json()["detail"]["code"] == "invalid_token"


def test_repeated_failed_logins_are_rate_limited_per_email(env):
    _verified_user(env)
    for attempt in range(8):
        assert (
            _login(env, password=f"yanlis-parola-{attempt}", ip=f"10.1.0.{attempt}").status_code
            == 401
        )
    limited = _login(env, ip="10.2.0.1")
    assert limited.status_code == 429
    assert limited.json()["detail"]["code"] == "rate_limited"


def test_account_deletion_removes_user_and_sessions(env):
    token = _verified_user(env)
    client = env["client"]
    client.put("/api/me/watchlist", headers=_bearer(token), json={"tickers": ["THYAO"]})
    wrong = client.post("/api/me/delete", headers=_bearer(token), json={"password": "yanlis-1234"})
    assert wrong.status_code == 400
    assert (
        client.post(
            "/api/me/delete", headers=_bearer(token), json={"password": PASSWORD}
        ).status_code
        == 200
    )
    assert client.get("/api/me", headers=_bearer(token)).status_code == 401
    with Session(env["db"]) as session:
        assert session.scalar(select(AppUser)) is None
        assert session.scalar(select(UserSession)) is None
        assert session.scalar(select(UserWatchlistItem)) is None


def test_admin_manages_invites_and_users(env):
    client = env["client"]
    assert client.get("/api/admin/users").status_code == 401

    created = client.post(
        "/api/admin/invites", headers=SERVICE, json={"note": "beta", "max_uses": 2}
    )
    assert created.status_code == 201
    invite = created.json()
    assert re.fullmatch(r"[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}", invite["code"])
    assert invite["state"] == "active" and invite["expires_at"]

    assert _register(env, invite=invite["code"]).status_code == 202
    revoked = client.delete(f"/api/admin/invites/{invite['id']}", headers=SERVICE)
    assert revoked.json()["state"] == "revoked"
    assert _register(env, email="ikinci@example.com", invite=invite["code"]).status_code == 422

    listing = client.get("/api/admin/users", headers=SERVICE).json()
    assert listing["total"] == 1 and listing["verified"] == 0 and listing["signups_24h"] == 1
    user_id = listing["users"][0]["id"]

    verified = client.patch(
        f"/api/admin/users/{user_id}", headers=SERVICE, json={"verify_email": True, "role": "admin"}
    )
    assert verified.json()["email_verified_at"] and verified.json()["role"] == "admin"
    token = _login(env).json()["token"]
    assert client.get("/api/me", headers=_bearer(token)).json()["role"] == "admin"

    client.patch(f"/api/admin/users/{user_id}", headers=SERVICE, json={"status": "DISABLED"})
    assert client.get("/api/me", headers=_bearer(token)).status_code == 401
    assert _login(env).json()["detail"]["code"] == "account_disabled"


def test_security_helpers():
    assert security.normalize_email("  Ayse@Example.COM ") == "ayse@example.com"
    assert security.normalize_email("ayse@localhost") is None
    assert security.normalize_email("a b@example.com") is None
    assert security.password_problem("aaaaaaaaaaaa") is not None
    assert security.password_problem("kisa1") is not None
    assert security.password_problem(PASSWORD) is None
    raw, digest = security.new_token()
    assert len(raw) >= 40 and security.hash_token(raw) == digest
    assert security.normalize_invite_code(" abcd-efgh ") == "ABCD-EFGH"
