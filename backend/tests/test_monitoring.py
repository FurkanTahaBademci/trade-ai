"""Sistem tazeligi ve webhook alarm regresyon testleri."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.monitoring import service


class FakeRedis:
    def __init__(self, values: dict[str, str] | None = None, *, acquired: bool = True):
        self.values = values or {}
        self.acquired = acquired
        self.deleted: list[str] = []

    async def mget(self, keys):
        return [self.values.get(key) for key in keys]

    async def set(self, key, value, **kwargs):
        return self.acquired

    async def delete(self, key):
        self.deleted.append(key)


class FakeResponse:
    def raise_for_status(self):
        return None


class FakeHttpClient:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def post(self, url, *, json):
        self.calls.append((url, json))
        return FakeResponse()


def test_freshness_prefers_newer_success_over_old_error():
    now = datetime(2026, 9, 7, 12, tzinfo=UTC)
    result = service.evaluate_freshness(
        last_success=(now - timedelta(minutes=2)).isoformat(),
        last_error=f"{(now - timedelta(minutes=5)).isoformat()} | RuntimeError('old')",
        max_age_seconds=600,
        now=now,
    )

    assert result["state"] == "healthy"
    assert result["age_seconds"] == 120


@pytest.mark.parametrize(
    ("success_age", "error_age", "expected"),
    [(700, None, "stale"), (None, 30, "error"), (None, None, "pending")],
)
def test_freshness_problem_states(success_age, error_age, expected):
    now = datetime(2026, 9, 7, 12, tzinfo=UTC)
    result = service.evaluate_freshness(
        last_success=(now - timedelta(seconds=success_age)).isoformat()
        if success_age is not None
        else None,
        last_error=(now - timedelta(seconds=error_age)).isoformat()
        if error_age is not None
        else None,
        max_age_seconds=600,
        now=now,
    )

    assert result["state"] == expected


async def test_monitoring_report_counts_stale_and_pending_components():
    now = datetime(2026, 9, 7, 12, tzinfo=UTC)
    recent = (now - timedelta(minutes=1)).isoformat()
    old = (now - timedelta(days=5)).isoformat()
    redis = FakeRedis(
        {
            "collector:kap:last_success": recent,
            "collector:news:last_success": old,
            "worker:last_heartbeat": recent,
        }
    )

    report = await service.get_monitoring_report(redis, now=now)

    assert report["status"] == "degraded"
    assert report["collectors"]["kap"]["state"] == "healthy"
    assert report["collectors"]["news"]["state"] == "stale"
    assert report["worker"]["state"] == "healthy"
    assert report["problem_count"] == 1
    assert report["pending_count"] == len(service.COLLECTOR_POLICIES) - 2


async def test_webhook_alert_is_delivered_with_structured_payload(monkeypatch):
    async def fake_resolve_settings(*args, **kwargs):
        return SimpleNamespace(
            n8n_webhook_url="https://n8n.example/webhook/trade-ai",
            monitoring_alert_cooldown_seconds=3600,
        )

    monkeypatch.setattr(service, "resolve_settings", fake_resolve_settings)
    redis = FakeRedis()
    client = FakeHttpClient()

    result = await service.send_webhook_alert(
        event_type="collector_failure",
        title="KAP hatasi",
        message="timeout",
        details={"collector": "kap"},
        redis=redis,
        client=client,
    )

    assert result == {"enabled": True, "delivered": True}
    assert client.calls[0][1]["source"] == "trade-ai"
    assert client.calls[0][1]["details"] == {"collector": "kap"}


async def test_webhook_alert_respects_cooldown(monkeypatch):
    async def fake_resolve_settings(*args, **kwargs):
        return SimpleNamespace(
            n8n_webhook_url="https://n8n.example/webhook/trade-ai",
            monitoring_alert_cooldown_seconds=3600,
        )

    monkeypatch.setattr(service, "resolve_settings", fake_resolve_settings)
    client = FakeHttpClient()

    result = await service.send_webhook_alert(
        event_type="component_unhealthy",
        title="Fiyat gecikmesi",
        message="stale",
        redis=FakeRedis(acquired=False),
        client=client,
    )

    assert result["reason"] == "deduplicated"
    assert client.calls == []
