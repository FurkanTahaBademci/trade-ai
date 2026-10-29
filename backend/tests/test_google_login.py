"""Google ile giris: ID token denetimi, hesap acma/eslestirme, baglama ve parolasiz hesap."""

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.auth import google, security
from app.auth.google import GoogleProfile, exchange_code, parse_id_token
from app.auth.security import hash_token
from app.auth.service import AuthError
from app.core import config
from app.core.db import Base, get_db
from app.main import app
from app.models import AppUser, InviteCode, UserIdentity, UserSession, UserToken

SERVICE = {"X-Admin-Token": "test-service-token"}
CLIENT_ID = "test-client.apps.googleusercontent.com"
NONCE = "nonce-value-123"
CODE = {"code": "auth-code", "code_verifier": "v" * 43, "nonce": NONCE}
# Sabit dizeden turetilir; gitleaks genel anahtar kuralina takilmasin.
FIRST_PASSWORD = "dogru-parola-123"
OTHER_PASSWORD = f"{FIRST_PASSWORD}-baska"
TABLES = [
    InviteCode.__table__,
    AppUser.__table__,
    UserSession.__table__,
    UserToken.__table__,
    UserIdentity.__table__,
]


def _jwt(claims: dict) -> str:
    def part(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'RS256'})}.{part(claims)}.c2ln"


def _claims(**overrides) -> dict:
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1001",
        "email": "Ayse@GoogleMail.com",
        "email_verified": True,
        "name": "Ayşe Yılmaz",
        "nonce": NONCE,
        "exp": int(datetime.now(UTC).timestamp()) + 600,
    }
    claims.update(overrides)
    return claims


def _google_settings():
    return config.get_settings().model_copy(
        update={
            "google_client_id": CLIENT_ID,
            "google_client_secret": "test-secret",
            "public_base_url": "https://trade.example.com",
        }
    )


# --- Saf denetimler ----------------------------------------------------------


def test_start_url_uses_pkce_and_callback():
    started = google.start(_google_settings())
    query = parse_qs(urlparse(started.url).query)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(started.code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert query["code_challenge"] == [challenge] and query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["https://trade.example.com/giris/google/callback"]
    assert query["state"] == [started.state] and query["nonce"] == [started.nonce]
    assert query["scope"] == ["openid email profile"]


def test_id_token_claims_are_checked():
    profile = parse_id_token(_jwt(_claims()), client_id=CLIENT_ID, nonce=NONCE)
    assert profile == GoogleProfile(subject="1001", email="ayse@googlemail.com", name="Ayşe Yılmaz")
    assert profile.authoritative
    workspace = parse_id_token(
        _jwt(_claims(email="can@sirket.com.tr", hd="sirket.com.tr")),
        client_id=CLIENT_ID,
        nonce=NONCE,
    )
    assert workspace.authoritative
    other = parse_id_token(_jwt(_claims(email="can@example.com")), client_id=CLIENT_ID, nonce=NONCE)
    assert not other.authoritative
    for bad in (
        _claims(aud="baska-istemci"),
        _claims(iss="https://evil.example.com"),
        _claims(nonce="baska"),
        _claims(exp=int(datetime.now(UTC).timestamp()) - 3600),
        _claims(sub=""),
    ):
        with pytest.raises(AuthError) as error:
            parse_id_token(_jwt(bad), client_id=CLIENT_ID, nonce=NONCE)
        assert error.value.code == "google_failed"
    with pytest.raises(AuthError) as error:
        parse_id_token(_jwt(_claims(email_verified=False)), client_id=CLIENT_ID, nonce=NONCE)
    assert error.value.code == "google_email_unverified"
    with pytest.raises(AuthError):
        parse_id_token("bozuk-token", client_id=CLIENT_ID, nonce=NONCE)


async def test_code_exchange_posts_secret_and_verifier():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(parse_qs(request.content.decode()))
        if seen[-1]["code"] == ["kullanilmis"]:
            return httpx.Response(400, json={"error": "invalid_grant"})
        return httpx.Response(200, json={"id_token": _jwt(_claims())})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        profile = await exchange_code(
            _google_settings(), code="iyi", code_verifier="v" * 43, nonce=NONCE, client=client
        )
        with pytest.raises(AuthError):
            await exchange_code(
                _google_settings(),
                code="kullanilmis",
                code_verifier="v" * 43,
                nonce=NONCE,
                client=client,
            )
    assert profile.email == "ayse@googlemail.com"
    assert seen[0]["client_secret"] == ["test-secret"] and seen[0]["code_verifier"] == ["v" * 43]
    assert seen[0]["redirect_uri"] == ["https://trade.example.com/giris/google/callback"]


# --- API ---------------------------------------------------------------------


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    async def get(self, key):
        return self.values.get(key)

    async def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key, seconds):
        return None


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / "google.db"
    sync_engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(sync_engine, tables=TABLES)
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}", poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    settings = config.get_settings()
    monkeypatch.setattr(settings, "admin_api_token", SERVICE["X-Admin-Token"])
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")
    redis = FakeRedis()
    monkeypatch.setattr("app.auth.ratelimit.get_redis", lambda: redis)
    monkeypatch.setattr(
        security, "_hasher", PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    )
    mode = {"value": "invite"}

    async def fake_resolve_settings():
        return config.get_settings().model_copy(update={"registration_mode": mode["value"]})

    monkeypatch.setattr("app.auth.service.resolve_settings", fake_resolve_settings)
    profile = {"value": GoogleProfile(subject="1001", email="ayse@googlemail.com", name="Ayşe")}

    async def fake_exchange(_settings, *, code, code_verifier, nonce, client=None):
        assert code == CODE["code"] and nonce == NONCE
        return profile["value"]

    monkeypatch.setattr(google, "exchange_code", fake_exchange)
    with TestClient(app) as client:
        yield {"client": client, "db": sync_engine, "mode": mode, "profile": profile}
    app.dependency_overrides.pop(get_db, None)
    sync_engine.dispose()


def _sign_in(env, **body):
    return env["client"].post(
        "/api/auth/google", headers=SERVICE, json={**CODE, "client_ip": "203.0.113.5", **body}
    )


def _user(
    env, email: str, *, verified: bool = True, password: str | None = "eski-parola-123"
) -> int:
    hashed = (
        PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(password)
        if password
        else None
    )
    with Session(env["db"]) as session:
        user = AppUser(
            email=email,
            password_hash=hashed,
            display_name="Yerel",
            role="user",
            status="ACTIVE",
            email_verified_at=datetime.now(UTC) if verified else None,
        )
        session.add(user)
        session.commit()
        return user.id


def _bearer(env, user_id: int) -> dict:
    now = datetime.now(UTC)
    with Session(env["db"]) as session:
        session.add(
            UserSession(
                user_id=user_id,
                token_hash=hash_token(f"oturum-{user_id}"),
                created_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(days=1),
            )
        )
        session.commit()
    return {"Authorization": f"Bearer oturum-{user_id}"}


def test_config_and_start_follow_client_settings(env, monkeypatch):
    client = env["client"]
    assert client.get("/api/auth/config", headers=SERVICE).json()["google_enabled"] is True
    started = client.post("/api/auth/google/start", headers=SERVICE).json()
    assert started["url"].startswith(google.AUTHORIZE_URL) and len(started["code_verifier"]) >= 43
    monkeypatch.setattr(config.get_settings(), "google_client_secret", "")
    assert client.get("/api/auth/config", headers=SERVICE).json()["google_enabled"] is False
    assert client.post("/api/auth/google/start", headers=SERVICE).status_code == 404
    assert client.post("/api/auth/google/start").status_code == 401


def test_new_google_account_needs_consent_and_invite(env):
    missing = _sign_in(env)
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "signup_required"
    no_invite = _sign_in(env, accept_terms=True)
    assert no_invite.json()["detail"]["code"] == "invalid_invite"
    with Session(env["db"]) as session:
        session.add(InviteCode(code="ABCD-EFGH-JKLM", note="", max_uses=1, used_count=0))
        session.commit()
    created = _sign_in(env, accept_terms=True, invite_code="abcd-efgh-jklm")
    assert created.status_code == 200
    user = created.json()["user"]
    assert user["email"] == "ayse@googlemail.com" and user["has_password"] is False
    assert user["email_verified"] is True and user["display_name"] == "Ayşe"
    again = _sign_in(env)  # ayni Google kimligi: kosul/davet gerekmez
    assert again.status_code == 200 and again.json()["user"]["id"] == user["id"]
    with Session(env["db"]) as session:
        assert session.scalar(select(UserIdentity.subject)) == "1001"
        assert session.scalar(select(InviteCode.used_count)) == 1


def test_open_and_closed_registration(env):
    env["mode"]["value"] = "closed"
    assert _sign_in(env, accept_terms=True).json()["detail"]["code"] == "registration_closed"
    env["mode"]["value"] = "open"
    assert _sign_in(env, accept_terms=True).status_code == 200


def test_existing_account_links_only_for_authoritative_email(env):
    gmail_user = _user(env, "ayse@googlemail.com")
    linked = _sign_in(env)
    assert linked.status_code == 200 and linked.json()["user"]["id"] == gmail_user
    assert linked.json()["user"]["has_password"] is True  # parola korunur

    _user(env, "can@example.com")
    env["profile"]["value"] = GoogleProfile(subject="2002", email="can@example.com", name="Can")
    refused = _sign_in(env)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "link_required"
    env["profile"]["value"] = GoogleProfile(
        subject="2002", email="can@example.com", name="Can", hosted_domain="example.com"
    )
    assert _sign_in(env).status_code == 200


def test_unverified_squatted_account_loses_foreign_password(env):
    squatted = _user(env, "ayse@googlemail.com", verified=False)
    _bearer(env, squatted)
    response = _sign_in(env)
    assert response.status_code == 200 and response.json()["user"]["has_password"] is False
    with Session(env["db"]) as session:
        user = session.get(AppUser, squatted)
        assert user.password_hash is None and user.email_verified_at is not None
        # Onceden acilmis oturum kapatildi; yalniz yeni Google oturumu kalir.
        assert session.scalar(
            select(UserSession.token_hash).where(UserSession.user_id == squatted)
        ) != hash_token(f"oturum-{squatted}")


def test_disabled_account_cannot_sign_in(env):
    user_id = _user(env, "ayse@googlemail.com")
    assert _sign_in(env).status_code == 200
    with Session(env["db"]) as session:
        session.get(AppUser, user_id).status = "DISABLED"
        session.commit()
    assert _sign_in(env).json()["detail"]["code"] == "account_disabled"


def test_link_and_unlink_from_account(env):
    client = env["client"]
    ayse = _bearer(env, _user(env, "ayse@example.com"))
    mehmet = _bearer(env, _user(env, "mehmet@example.com"))
    env["profile"]["value"] = GoogleProfile(
        subject="3003", email="ayse.kisisel@googlemail.com", name=""
    )
    assert client.get("/api/me/identities", headers=ayse).json() == []
    linked = client.post("/api/me/identities/google", headers=ayse, json=CODE)
    assert linked.status_code == 200 and linked.json()[0]["email"] == "ayse.kisisel@googlemail.com"
    assert client.post("/api/me/identities/google", headers=ayse, json=CODE).status_code == 200
    taken = client.post("/api/me/identities/google", headers=mehmet, json=CODE)
    assert taken.json()["detail"]["code"] == "identity_in_use"
    # Bagli kimlikle giris artik o hesaba acilir (e-posta farkli olsa da).
    assert _sign_in(env).json()["user"]["email"] == "ayse@example.com"
    assert client.delete("/api/me/identities/google", headers=ayse).status_code == 204
    assert client.delete("/api/me/identities/google", headers=ayse).status_code == 404


def test_passwordless_account_sets_password_and_deletes_with_email(env):
    env["mode"]["value"] = "open"
    user_id = _sign_in(env, accept_terms=True).json()["user"]["id"]
    headers = _bearer(env, user_id)
    client = env["client"]
    blocked = client.delete("/api/me/identities/google", headers=headers)
    assert blocked.json()["detail"]["code"] == "password_required"
    wrong = client.post("/api/me/delete", headers=headers, json={"email": "baska@googlemail.com"})
    assert wrong.json()["detail"]["code"] == "confirmation_mismatch"
    changed = client.post(
        "/api/me/password",
        headers=headers,
        json={"current_password": "", "new_password": FIRST_PASSWORD},
    )
    assert changed.status_code == 200
    assert client.get("/api/me", headers=headers).json()["has_password"] is True
    # Artik parola var: mevcut parola istenir.
    again = client.post(
        "/api/me/password",
        headers=headers,
        json={"current_password": "", "new_password": OTHER_PASSWORD},
    )
    assert again.status_code == 400
    assert client.delete("/api/me/identities/google", headers=headers).status_code == 204
    gone = client.post("/api/me/delete", headers=headers, json={"password": FIRST_PASSWORD})
    assert gone.status_code == 200
