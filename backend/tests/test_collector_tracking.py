"""Collector saglik kayitlari icin regresyon testleri."""

from app.collectors import base


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str):
        self.values[key] = value


class PartialCollector(base.BaseCollector):
    name = "partial-test"

    async def run(self) -> dict:
        return {
            "new": 2,
            "source_failures": {"source-b": "timeout", "source-a": "HTTP 500"},
        }


async def test_partial_source_failure_is_visible_in_health_tracking(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(base, "get_redis", lambda: redis)

    result = await PartialCollector().run_tracked()

    assert result["new"] == 2
    assert "collector:partial-test:last_success" in redis.values
    error = redis.values["collector:partial-test:last_error"]
    assert "Kismi kaynak hatasi: source-a, source-b" in error
