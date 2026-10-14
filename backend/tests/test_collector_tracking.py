"""Collector saglik kayitlari icin regresyon testleri."""

from app.collectors import base


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str):
        self.values[key] = value

    async def delete(self, key: str):
        self.values.pop(key, None)


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


class SkippedCollector(base.BaseCollector):
    name = "skipped-test"

    def __init__(self, skipped: str | None):
        super().__init__()
        self.skipped = skipped

    async def run(self) -> dict:
        return {"skipped": self.skipped, "rows": 0} if self.skipped else {"rows": 3}


async def test_skipped_run_is_recorded_and_cleared_after_real_run(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(base, "get_redis", lambda: redis)

    await SkippedCollector("EVDS_API_KEY tanimli degil").run_tracked()
    assert redis.values["collector:skipped-test:skipped"].endswith("EVDS_API_KEY tanimli degil")

    await SkippedCollector(None).run_tracked()
    assert "collector:skipped-test:skipped" not in redis.values
