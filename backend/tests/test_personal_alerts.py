"""Kisisel bildirimler: Telegram baglama, anlik etiket degisimi, gunluk ozet ve API.

Telegram Bot API httpx.MockTransport ile, Redis bellek ici sahte ile taklit edilir.
"""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.alerts import personal
from app.alerts.personal import (
    USER_LABEL_STATE_KEY,
    UserDigest,
    build_user_digest,
    create_link,
    evaluate_user_label_alerts,
    handle_update,
    poll_telegram,
    send_user_digests,
)
from app.auth.security import hash_token
from app.core import config
from app.core.db import Base, get_db
from app.main import app
from app.models import (
    AppUser,
    CompositeSignalSnapshot,
    IndexDaily,
    Instrument,
    PaperOrder,
    PaperPortfolio,
    PaperPortfolioSnapshot,
    PaperPosition,
    PaperTrade,
    UserAlertPref,
    UserSession,
    UserToken,
    UserWatchlistItem,
)
from app.signals.service import MODEL_VERSION

TABLES = [
    AppUser.__table__,
    UserSession.__table__,
    UserToken.__table__,
    UserAlertPref.__table__,
    UserWatchlistItem.__table__,
    Instrument.__table__,
    PaperPortfolio.__table__,
    PaperPosition.__table__,
    PaperTrade.__table__,
    PaperOrder.__table__,
    PaperPortfolioSnapshot.__table__,
    CompositeSignalSnapshot.__table__,
    IndexDaily.__table__,
]
BOT_TOKEN = "123456:test-bot-token"
TODAY = date(2026, 10, 28)
YESTERDAY = date(2026, 10, 27)
NOW = datetime(2026, 10, 28, 16, 30, tzinfo=UTC)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return None
        self.values[key] = str(value)
        return True

    async def delete(self, key):
        self.values.pop(key, None)

    async def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    async def expire(self, key, seconds):
        return None

    async def hgetall(self, key):
        return dict(self.values.get(key, {}))

    async def hset(self, key, mapping):
        self.values.setdefault(key, {}).update(mapping)


class FakeTelegram:
    """sendMessage/getMe/getUpdates cagrilarini kaydeder; yanitlar ayarlanabilir."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.updates: list[dict] = []
        self.update_offsets: list[int | None] = []
        self.status = 200
        self.blocked_chats: set[str] = set()

    def handler(self, request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        body = json.loads(request.content or b"{}")
        if method == "getMe":
            return httpx.Response(200, json={"ok": True, "result": {"username": "tradeai_bot"}})
        if method == "getUpdates":
            self.update_offsets.append(body.get("offset"))
            if self.status != 200:
                return httpx.Response(self.status, json={"ok": False, "description": "Conflict"})
            pending = [u for u in self.updates if u["update_id"] >= (body.get("offset") or 0)]
            return httpx.Response(200, json={"ok": True, "result": pending})
        if str(body.get("chat_id")) in self.blocked_chats:
            return httpx.Response(
                403, json={"ok": False, "description": "Forbidden: bot was blocked by the user"}
            )
        if self.status != 200:
            return httpx.Response(self.status, json={"ok": False, "description": "Bad Gateway"})
        self.sent.append(body)
        return httpx.Response(200, json={"ok": True, "result": {}})

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


def _settings(**values):
    base = {
        "user_alerts_enabled": True,
        "alerts_telegram_bot_token": BOT_TOKEN,
        "tz": "Europe/Istanbul",
    }
    return config.get_settings().model_copy(update={**base, **values})


def _message(update_id: int, chat_id: int, text: str, username: str = "ayse_tg") -> dict:
    return {
        "update_id": update_id,
        "message": {
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "username": username},
            "text": text,
        },
    }


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / "alerts.db"
    sync_engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(sync_engine, tables=TABLES)
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}", poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    with Session(sync_engine) as session:
        for user_id, email in (
            (1, "ayse@example.com"),
            (2, "mehmet@example.com"),
            (3, "zeynep@example.com"),
            (4, "can@example.com"),
        ):
            session.add(
                AppUser(
                    id=user_id,
                    email=email,
                    display_name="",
                    role="user",
                    status="ACTIVE",
                    email_verified_at=now,
                )
            )
            session.flush()
            session.add(
                UserSession(
                    user_id=user_id,
                    token_hash=hash_token(f"token-{user_id}"),
                    created_at=now,
                    last_seen_at=now,
                    expires_at=now + timedelta(days=1),
                )
            )
        session.commit()
    yield {"db": sync_engine, "factory": factory, "redis": FakeRedis(), "telegram": FakeTelegram()}
    sync_engine.dispose()


def _link(env, user_id: int, chat_id: str, **pref) -> None:
    with Session(env["db"]) as session:
        session.merge(
            UserAlertPref(
                user_id=user_id,
                telegram_chat_id=chat_id,
                telegram_instant=pref.get("instant", True),
                telegram_digest=pref.get("digest", True),
                email_digest=pref.get("email", False),
            )
        )
        session.commit()


def _watch(env, user_id: int, *tickers: str) -> None:
    with Session(env["db"]) as session:
        session.add_all(UserWatchlistItem(user_id=user_id, ticker=t) for t in tickers)
        session.commit()


def _portfolio(
    env, owner_id: int, name: str = "Benim portföyüm", holding: str | None = None
) -> int:
    with Session(env["db"]) as session:
        portfolio = PaperPortfolio(
            name=name,
            owner_id=owner_id,
            kind="MANUAL",
            strategy_version="manual-v1",
            status="ACTIVE",
            initial_cash=Decimal(100000),
            cash_balance=Decimal(50000),
        )
        session.add(portfolio)
        session.flush()
        if holding:
            session.add(
                PaperPosition(
                    portfolio_id=portfolio.id,
                    ticker=holding,
                    quantity=Decimal(10),
                    average_cost=Decimal(100),
                    last_price=Decimal(110),
                    market_value=Decimal(1100),
                    unrealized_pnl=Decimal(100),
                )
            )
        session.commit()
        return portfolio.id


def _signals(env, day: date, labels: dict[str, tuple[str, float]], start_id: int) -> None:
    with Session(env["db"]) as session:
        for offset, (ticker, (label, score)) in enumerate(sorted(labels.items())):
            session.add(
                CompositeSignalSnapshot(
                    id=start_id + offset,
                    ticker=ticker,
                    as_of_date=day,
                    model_version=MODEL_VERSION,
                    composite_score=Decimal(str(score)),
                    signal_label=label,
                    confidence=Decimal("0.5"),
                    coverage_count=3,
                    component_scores={},
                    component_weights={},
                    evidence={},
                )
            )
        session.commit()


# --- Telegram baglama --------------------------------------------------------


async def test_link_code_connects_chat_and_stop_unlinks(env):
    telegram, redis = env["telegram"], env["redis"]
    async with env["factory"]() as db, telegram.client() as client:
        user = await db.get(AppUser, 1)
        url, expires_at = await create_link(
            db, user, settings=_settings(), redis=redis, client=client
        )
    assert url.startswith("https://t.me/tradeai_bot?start=") and expires_at > datetime.now(UTC)
    code = url.rpartition("=")[2]

    async with env["factory"]() as db:
        chat_id, reply = await handle_update(db, _message(1, 555, f"/start {code}"))
    assert chat_id == "555" and "a***@example.com" in reply
    with Session(env["db"]) as session:
        pref = session.get(UserAlertPref, 1)
        assert pref.telegram_chat_id == "555" and pref.telegram_username == "ayse_tg"

    async with env["factory"]() as db:
        _, reused = await handle_update(db, _message(2, 777, f"/start {code}"))
        _, plain = await handle_update(db, _message(3, 777, "/start"))
        ignored = await handle_update(db, _message(4, 777, "merhaba"))
        group = {"update_id": 5, "message": {"chat": {"id": -1, "type": "group"}, "text": "/stop"}}
        assert await handle_update(db, group) is None
    assert reused == personal.INVALID_CODE_TEXT and plain == personal.WELCOME_TEXT
    assert ignored is None

    async with env["factory"]() as db:
        _, stopped = await handle_update(db, _message(6, 555, "/stop@tradeai_bot"))
        _, again = await handle_update(db, _message(7, 555, "/stop"))
    assert stopped == personal.STOPPED_TEXT and again == personal.NOT_LINKED_TEXT
    with Session(env["db"]) as session:
        assert session.get(UserAlertPref, 1).telegram_chat_id is None


async def test_link_needs_configured_bot(env):
    async with env["factory"]() as db, env["telegram"].client() as client:
        user = await db.get(AppUser, 1)
        for settings in (
            _settings(alerts_telegram_bot_token=""),
            _settings(user_alerts_enabled=False),
        ):
            assert (
                await create_link(db, user, settings=settings, redis=env["redis"], client=client)
                is None
            )


async def test_poll_processes_updates_once_and_pauses_on_webhook_conflict(env):
    telegram, redis = env["telegram"], env["redis"]
    telegram.updates = [_message(40, 901, "/start"), _message(41, 902, "/help")]
    async with telegram.client() as client:
        first = await poll_telegram(
            env["factory"], settings=_settings(), redis=redis, client=client
        )
        second = await poll_telegram(
            env["factory"], settings=_settings(), redis=redis, client=client
        )
    assert first == {"status": "ok", "updates": 2, "handled": 2}
    assert second["updates"] == 0 and telegram.update_offsets == [None, 42]
    assert [message["chat_id"] for message in telegram.sent] == ["901", "902"]
    assert redis.values.get(personal.POLL_LOCK_KEY) is None

    redis.values.pop(personal.POLL_OFFSET_KEY)
    telegram.status = 409
    async with telegram.client() as client:
        conflict = await poll_telegram(
            env["factory"], settings=_settings(), redis=redis, client=client
        )
        paused = await poll_telegram(
            env["factory"], settings=_settings(), redis=redis, client=client
        )
    assert conflict["error"] == "conflict" and paused == {"status": "paused"}


# --- Anlik etiket degisimi ---------------------------------------------------


async def test_label_changes_reach_watchers_and_holders_once(env):
    _link(env, 1, "101")  # THYAO izliyor
    _link(env, 2, "102")  # ASELS tutuyor
    _link(env, 4, "104", instant=False)  # anlik bildirimi kapali
    _watch(env, 1, "THYAO", "GARAN")
    _watch(env, 3, "THYAO")  # Telegram bagli degil
    _watch(env, 4, "THYAO")
    _portfolio(env, 2, holding="ASELS")
    redis, telegram = env["redis"], env["telegram"]
    redis.values[USER_LABEL_STATE_KEY] = {
        "THYAO": "POSITIVE",
        "ASELS": "NEUTRAL",
        "GARAN": "NEUTRAL",
    }
    loaded = (
        TODAY,
        {
            "THYAO": {"label": "VERY_POSITIVE", "score": 86.4, "as_of_date": TODAY.isoformat()},
            "ASELS": {"label": "NEGATIVE", "score": 31.0, "as_of_date": TODAY.isoformat()},
            "GARAN": {"label": "NEUTRAL", "score": 50.0, "as_of_date": TODAY.isoformat()},
            "AKBNK": {"label": "POSITIVE", "score": 70.0, "as_of_date": TODAY.isoformat()},
        },
    )
    async with env["factory"]() as db, telegram.client() as client:
        stats = await evaluate_user_label_alerts(
            db, settings=_settings(), redis=redis, client=client, loaded=loaded
        )
        repeat = await evaluate_user_label_alerts(
            db, settings=_settings(), redis=redis, client=client, loaded=loaded
        )
    assert stats["user_label_alerts"] == 2 and repeat["user_label_alerts"] == 0
    by_chat = {message["chat_id"]: message["text"] for message in telegram.sent}
    assert set(by_chat) == {"101", "102"}
    assert "THYAO: Olumlu → Çok olumlu (86,4)" in by_chat["101"] and "GARAN" not in by_chat["101"]
    assert "ASELS: Nötr → Olumsuz (31,0) · portföyünde" in by_chat["102"]
    assert redis.values[USER_LABEL_STATE_KEY]["AKBNK"] == "POSITIVE"


async def test_label_state_waits_when_telegram_is_down_and_blocked_chat_unlinks(env):
    _link(env, 1, "101")
    _link(env, 2, "102")
    _watch(env, 1, "THYAO")
    _watch(env, 2, "THYAO")
    redis, telegram = env["redis"], env["telegram"]
    redis.values[USER_LABEL_STATE_KEY] = {"THYAO": "NEUTRAL"}
    loaded = (TODAY, {"THYAO": {"label": "POSITIVE", "score": 72.0, "as_of_date": "2026-10-28"}})
    telegram.status = 502
    async with env["factory"]() as db, telegram.client() as client:
        down = await evaluate_user_label_alerts(
            db, settings=_settings(), redis=redis, client=client, loaded=loaded
        )
    assert down == {"user_label_alerts": 0, "user_label_failures": 2}
    assert redis.values[USER_LABEL_STATE_KEY]["THYAO"] == "NEUTRAL"  # sonraki turda yeniden

    telegram.status = 200
    telegram.blocked_chats = {"102"}
    async with env["factory"]() as db, telegram.client() as client:
        recovered = await evaluate_user_label_alerts(
            db, settings=_settings(), redis=redis, client=client, loaded=loaded
        )
    assert recovered["user_label_alerts"] == 1 and telegram.sent[0]["chat_id"] == "101"
    assert redis.values[USER_LABEL_STATE_KEY]["THYAO"] == "POSITIVE"
    with Session(env["db"]) as session:
        assert session.get(UserAlertPref, 2).telegram_chat_id is None


# --- Gunluk ozet -------------------------------------------------------------


def _digest_data(env) -> int:
    portfolio_id = _portfolio(env, 1, name="Manuel deneme", holding="ASELS")
    with Session(env["db"]) as session:
        session.add_all(
            [
                IndexDaily(index_code="XU100", date=YESTERDAY, value=Decimal(10000)),
                IndexDaily(index_code="XU100", date=TODAY, value=Decimal(10150)),
            ]
        )
        for day, equity, total in ((YESTERDAY, "100000", "0"), (TODAY, "102000", "2")):
            session.add(
                PaperPortfolioSnapshot(
                    portfolio_id=portfolio_id,
                    snapshot_date=day,
                    cash_balance=Decimal(50000),
                    positions_value=Decimal(equity) - 50000,
                    total_equity=Decimal(equity),
                    realized_pnl=Decimal(0),
                    unrealized_pnl=Decimal(0),
                    total_return_pct=Decimal(total),
                    position_count=1,
                    weights={},
                )
            )
        for key, side, ticker, reason in (
            ("k1", "BUY", "ASELS", None),
            ("k2", "SELL", "SASA", "stop_loss"),
        ):
            session.add(
                PaperTrade(
                    execution_key=key,
                    portfolio_id=portfolio_id,
                    ticker=ticker,
                    strategy_version="manual-v1",
                    trade_date=TODAY,
                    side=side,
                    quantity=Decimal(10),
                    price=Decimal(100),
                    gross_amount=Decimal(1000),
                    fee_amount=Decimal(1),
                    reason="test",
                    exit_reason=reason,
                )
            )
        session.add(
            PaperOrder(
                portfolio_id=portfolio_id,
                ticker="KCHOL",
                side="BUY",
                amount=Decimal(5000),
                status="REJECTED",
                not_before=YESTERDAY,
                note="7 gün içinde gerçekleşmedi",
                updated_at=NOW - timedelta(hours=1),
            )
        )
        session.commit()
    _watch(env, 1, "THYAO")
    _signals(env, YESTERDAY, {"THYAO": ("NEUTRAL", 55.0), "ASELS": ("POSITIVE", 70.0)}, 1)
    _signals(env, TODAY, {"THYAO": ("POSITIVE", 71.2), "ASELS": ("POSITIVE", 72.0)}, 10)
    return portfolio_id


async def test_user_digest_goes_once_per_trading_day(env, monkeypatch):
    _digest_data(env)
    _link(env, 1, "101", email=True)
    _link(env, 2, "102")  # portfoy ve izleme listesi yok: bos ozet gitmez
    with Session(env["db"]) as session:
        session.add(UserAlertPref(user_id=3, telegram_digest=False, email_digest=False))
        session.commit()
    mails: list = []

    async def capture(mail):
        mails.append(mail)
        return True

    monkeypatch.setattr(personal, "enqueue_mail", capture)
    telegram = env["telegram"]
    async with telegram.client() as client:
        result = await send_user_digests(
            env["factory"], settings=_settings(), client=client, now=NOW
        )
        again = await send_user_digests(
            env["factory"], settings=_settings(), client=client, now=NOW
        )
    assert result["recipients"] == 2 and result["telegram"] == 1 and result["email"] == 1
    assert result["empty"] == 1 and again["recipients"] == 0
    text = telegram.sent[0]["text"]
    assert telegram.sent[0]["chat_id"] == "101" and text == mails[0].text.split("\n\nBildirim")[0]
    assert "BIST100: 10.150,00 (+%1,5)" in text
    assert "Manuel deneme: ₺102.000 · gün +%2,0 · toplam +%2,0" in text
    assert "İşlemler: AL ASELS, SAT SASA (zarar-kes)" in text
    assert "Reddedilen emir: AL KCHOL — 7 gün içinde gerçekleşmedi" in text
    assert "THYAO: Nötr → Olumlu (71,2)" in text and "ASELS:" not in text.split("etiket")[-1]
    assert mails[0].to == "ayse@example.com" and "/hesap/bildirimler" in mails[0].text
    with Session(env["db"]) as session:
        assert {p.user_id: p.last_digest_on for p in session.scalars(select(UserAlertPref))} == {
            1: TODAY,
            2: TODAY,
            3: None,
        }


async def test_user_digest_skips_stale_data_and_disabled_setting(env):
    _digest_data(env)
    _link(env, 1, "101")
    async with env["telegram"].client() as client:
        stale = await send_user_digests(
            env["factory"], settings=_settings(), client=client, now=NOW + timedelta(days=10)
        )
        off = await send_user_digests(
            env["factory"], settings=_settings(user_alerts_enabled=False), client=client, now=NOW
        )
    assert stale["status"] == "stale" and off == {"status": "disabled"}
    assert env["telegram"].sent == []


def test_digest_text_without_portfolios_mentions_quiet_watchlist():
    text = build_user_digest(
        UserDigest(as_of=TODAY, index_value=9876.5, index_change_pct=-0.04, watch_count=3)
    )
    assert "BIST100: 9.876,50 (%0,0)" in text
    assert "İzlediğin 3 hissede etiket değişimi yok." in text
    assert text.endswith("yatırım tavsiyesi değildir.")


# --- API ---------------------------------------------------------------------


@pytest.fixture
def api(env, monkeypatch):
    async def override_db():
        async with env["factory"]() as session:
            yield session

    state = {"settings": _settings()}

    async def fake_resolve_settings(**_kwargs):
        return state["settings"]

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.api.routers.my_alerts.httpx.AsyncClient",
        lambda **_kwargs: real_client(transport=httpx.MockTransport(env["telegram"].handler)),
    )
    monkeypatch.setattr("app.api.routers.my_alerts.resolve_settings", fake_resolve_settings)
    monkeypatch.setattr("app.api.routers.my_alerts.get_redis", lambda: env["redis"])
    monkeypatch.setattr("app.auth.ratelimit.get_redis", lambda: env["redis"])
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield {"client": client, "state": state}
    app.dependency_overrides.pop(get_db, None)


AYSE = {"Authorization": "Bearer token-1"}
MEHMET = {"Authorization": "Bearer token-2"}


def test_preferences_api_defaults_and_update(api):
    client = api["client"]
    assert client.get("/api/me/alerts").status_code == 401
    defaults = client.get("/api/me/alerts", headers=AYSE).json()
    assert defaults["telegram_available"] is True and defaults["telegram_linked"] is False
    assert (
        defaults["telegram_instant"]
        and defaults["telegram_digest"]
        and not defaults["email_digest"]
    )
    updated = client.put(
        "/api/me/alerts",
        headers=AYSE,
        json={"telegram_instant": False, "telegram_digest": True, "email_digest": True},
    ).json()
    assert updated["telegram_instant"] is False and updated["email_digest"] is True
    assert client.get("/api/me/alerts", headers=MEHMET).json()["email_digest"] is False


def test_link_check_test_and_unlink_api(api, env):
    client = api["client"]
    link = client.post("/api/me/alerts/telegram/link", headers=AYSE)
    assert link.status_code == 200
    code = link.json()["url"].rpartition("=")[2]
    assert client.post("/api/me/alerts/test", headers=AYSE).json()["detail"]["code"] == "not_linked"
    env["telegram"].updates = [_message(7, 31337, f"/start {code}")]
    checked = client.post("/api/me/alerts/telegram/check", headers=AYSE).json()
    assert checked["telegram_linked"] is True and checked["telegram_username"] == "ayse_tg"
    assert client.get("/api/me/alerts", headers=MEHMET).json()["telegram_linked"] is False
    assert client.post("/api/me/alerts/test", headers=AYSE).json()["status"] == "sent"
    assert env["telegram"].sent[-1]["chat_id"] == "31337"
    assert client.delete("/api/me/alerts/telegram", headers=AYSE).status_code == 204
    assert client.get("/api/me/alerts", headers=AYSE).json()["telegram_linked"] is False


def test_link_api_reports_unavailable_bot_and_rate_limits(api):
    client = api["client"]
    api["state"]["settings"] = _settings(alerts_telegram_bot_token="")
    unavailable = client.post("/api/me/alerts/telegram/link", headers=AYSE)
    assert unavailable.status_code == 503
    assert client.get("/api/me/alerts", headers=AYSE).json()["telegram_available"] is False
    api["state"]["settings"] = _settings()
    codes = [
        client.post("/api/me/alerts/telegram/link", headers=MEHMET).status_code for _ in range(11)
    ]
    assert codes[:10] == [200] * 10 and codes[10] == 429
