"""Bildirim kanallari, dedupe ve olay uretici testleri (agsiz, Redis'siz)."""

from datetime import date

import httpx
import pytest

from app.alerts import service
from app.alerts.channels import AlertMessage, configured_channels, deliver
from app.core.config import Settings
from app.core.dynamic_settings import get_setting_statuses
from app.main import app


class FakeRedis:
    def __init__(self):
        self.keys: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.keys:
            return None
        self.keys[key] = value
        return True

    async def delete(self, key):
        self.keys.pop(key, None)
        self.hashes.pop(key, None)

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    async def hset(self, key, mapping):
        self.hashes.setdefault(key, {}).update(mapping)


def _settings(**overrides) -> Settings:
    fields = {
        "alerts_enabled": True,
        "alerts_telegram_bot_token": "123:SECRET",
        "alerts_telegram_chat_id": "42",
        "alerts_webhook_url": "https://hooks.example/alert",
        **overrides,
    }
    return Settings(**fields)


def _client(status: int = 200, calls: list | None = None) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        return httpx.Response(status, json={"ok": True}, request=request)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


ALERT = AlertMessage(event_type="t", title="Başlık", message="Mesaj", severity="warning")


def test_alert_test_route_is_registered():
    assert "/api/settings/alerts/test" in set(app.openapi()["paths"])


def test_configured_channels_requires_complete_telegram_pair():
    assert configured_channels(Settings(alerts_telegram_bot_token="x")) == []
    assert configured_channels(_settings(alerts_webhook_url="")) == ["telegram"]
    assert configured_channels(_settings()) == ["telegram", "webhook"]


@pytest.mark.asyncio
async def test_deliver_posts_telegram_and_webhook_payloads():
    calls: list[httpx.Request] = []
    async with _client(calls=calls) as client:
        results = await deliver(ALERT, _settings(), client)

    assert [item["ok"] for item in results] == [True, True]
    telegram, webhook = calls
    assert str(telegram.url) == "https://api.telegram.org/bot123:SECRET/sendMessage"
    assert b'"chat_id":"42"' in telegram.content.replace(b" ", b"")
    assert b'"event_type":"t"' in webhook.content.replace(b" ", b"")


@pytest.mark.asyncio
async def test_failed_channel_never_raises_and_hides_token():
    async with _client(status=500) as client:
        results = await deliver(ALERT, _settings(alerts_webhook_url=""), client)

    assert results[0]["ok"] is False
    assert "SECRET" not in results[0]["error"]


@pytest.mark.asyncio
async def test_dispatch_is_idempotent_for_same_event():
    redis, calls = FakeRedis(), []
    async with _client(calls=calls) as client:
        kwargs = {"settings": _settings(), "redis": redis, "client": client}
        first = await service.dispatch_alert(ALERT, dedupe_key="e1", **kwargs)
        second = await service.dispatch_alert(ALERT, dedupe_key="e1", **kwargs)

    assert first["delivered"] is True
    assert second == {"delivered": False, "reason": "deduplicated"}
    assert len(calls) == 2  # ilk gonderimde telegram + webhook, ikincide sifir


def _trade(**overrides):
    return {
        "portfolio": "Ana",
        "ticker": "THYAO",
        "side": "SELL",
        "quantity": 100.0,
        "price": 250.5,
        "trade_date": "2026-10-08",
        "reason": "Zarar-kes: -8.10% <= -8%",
        "exit_reason": "stop_loss",
        "realized_pnl": -1250.0,
        **overrides,
    }


def test_paper_trade_alert_marks_risk_exits_as_warning():
    stop = service.paper_trade_alert(_trade())
    assert stop.severity == "warning"
    assert "satıldı" in stop.title
    assert "-1,250.00" in stop.message

    signal_exit = service.paper_trade_alert(_trade(exit_reason="signal"))
    buy = service.paper_trade_alert(
        _trade(side="BUY", exit_reason=None, realized_pnl=None, reason="Bilesik skor 80")
    )
    assert signal_exit.severity == "info"
    assert buy.severity == "info"
    assert "alındı" in buy.title
    assert "K/Z" not in buy.message


@pytest.mark.asyncio
async def test_dispatch_releases_key_when_all_channels_fail():
    redis = FakeRedis()
    async with _client(status=500) as client:
        result = await service.dispatch_alert(
            ALERT, dedupe_key="e1", settings=_settings(), redis=redis, client=client
        )

    assert result["reason"] == "delivery_failed"
    assert redis.keys == {}


@pytest.mark.asyncio
async def test_dispatch_disabled_sends_nothing():
    calls: list[httpx.Request] = []
    async with _client(calls=calls) as client:
        result = await service.dispatch_alert(
            ALERT,
            dedupe_key="e1",
            settings=_settings(alerts_enabled=False),
            redis=FakeRedis(),
            client=client,
        )

    assert result["reason"] == "disabled"
    assert calls == []


def test_label_changes_skip_first_observation_and_unchanged():
    current = {
        "AAA": {"label": "POSITIVE", "score": 61.0, "as_of_date": "2026-10-01"},
        "BBB": {"label": "NEUTRAL", "score": 50.0, "as_of_date": "2026-10-01"},
        "CCC": {"label": "NEGATIVE", "score": 30.0, "as_of_date": "2026-10-01"},
    }
    changes = service.detect_label_changes({"AAA": "NEUTRAL", "BBB": "NEUTRAL"}, current)

    assert [(c["ticker"], c["from"], c["to"]) for c in changes] == [("AAA", "NEUTRAL", "POSITIVE")]


def test_parse_watch_tickers_normalizes_input():
    assert service.parse_watch_tickers(" thyao, garan;;asels ") == {"THYAO", "GARAN", "ASELS"}


@pytest.mark.asyncio
async def test_health_alerts_dedupe_per_component_state():
    redis, calls = FakeRedis(), []
    report = {
        "collectors": {"kap": {"name": "kap", "label": "KAP", "state": "error"}},
        "worker": {"name": "worker", "label": "ARQ worker", "state": "healthy"},
    }
    async with _client(calls=calls) as client:
        kwargs = {"settings": _settings(), "redis": redis, "client": client, "report": report}
        first = await service.evaluate_health_alerts(**kwargs)
        second = await service.evaluate_health_alerts(**kwargs)

    assert (first, second) == (1, 0)


@pytest.mark.asyncio
async def test_signal_alerts_label_change_and_high_score_once(monkeypatch):
    scores = {
        "THYAO": {"label": "POSITIVE", "score": 88.0, "as_of_date": "2026-10-01"},
        "GARAN": {"label": "NEUTRAL", "score": 50.0, "as_of_date": "2026-10-01"},
    }

    async def fake_scores(session):
        return date(2026, 10, 1), scores

    async def fake_watched(session, settings):
        return {"THYAO", "GARAN"}

    monkeypatch.setattr(service, "_load_scores", fake_scores)
    monkeypatch.setattr(service, "_watched_tickers", fake_watched)
    redis, calls = FakeRedis(), []
    redis.hashes[service.LABEL_STATE_KEY] = {"THYAO": "NEUTRAL", "GARAN": "NEUTRAL"}
    async with _client(calls=calls) as client:
        kwargs = {"settings": _settings(alerts_webhook_url=""), "redis": redis, "client": client}
        first = await service.evaluate_signal_alerts(None, **kwargs)
        second = await service.evaluate_signal_alerts(None, **kwargs)

    assert first == {"label_changes": 1, "high_scores": 1}
    assert second == {"label_changes": 0, "high_scores": 0}
    assert len(calls) == 2
    assert redis.hashes[service.LABEL_STATE_KEY]["THYAO"] == "POSITIVE"


@pytest.mark.asyncio
async def test_alert_secrets_are_masked_in_setting_statuses():
    class SettingsRedis:
        async def hgetall(self, key):
            if key.endswith("alerts_telegram_bot_token"):
                return {"value": "123456:ABCDEF-secret", "updated_at": "x"}
            if key.endswith("alerts_telegram_chat_id"):
                return {"value": "987654321", "updated_at": "x"}
            return {}

    statuses = {s["key"]: s for s in await get_setting_statuses(redis=SettingsRedis())}

    assert statuses["alerts_telegram_bot_token"]["preview"] == "••••cret"
    assert "987654" not in statuses["alerts_telegram_chat_id"]["preview"]
    assert statuses["alerts_enabled"]["preview"] == "false"
