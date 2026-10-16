"""Gecmisi kisa hisselerin fiyat doldurmasi ve skor yenileme isareti (ag/DB yok)."""

from contextlib import asynccontextmanager
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.collectors import prices
from app.tasks import jobs

TODAY = date(2026, 10, 16)


class FakeRedis:
    def __init__(self, attempted=()):
        self.values = {f"prices:backfill:attempted:{t}": "1" for t in attempted}
        self.values["signals:backfill:attempted:v3"] = "x"

    async def mget(self, keys):
        return [self.values.get(key) for key in keys]

    async def set(self, key, value, ex=None):
        self.values[key] = value

    async def delete(self, key):
        self.values.pop(key, None)


@pytest.fixture
def harness(monkeypatch):
    state = SimpleNamespace(short=[], calls=[], rows=0, redis=FakeRedis())

    async def short_history(today):
        return state.short

    @asynccontextmanager
    async def session_factory():
        yield object()

    class Collector:
        def __init__(self, session, tickers=None, start_date=None):
            state.calls.append((tickers, start_date))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def run(self):
            return {"rows_upserted": state.rows, "failed_tickers": []}

    monkeypatch.setattr(jobs, "_short_history_tickers", short_history)
    monkeypatch.setattr(jobs, "session_factory", session_factory)
    monkeypatch.setattr(jobs, "get_redis", lambda: state.redis)
    monkeypatch.setattr(prices, "PriceCollector", Collector)
    return state


async def test_short_histories_are_backfilled_and_signals_marked_for_refresh(harness):
    harness.short, harness.rows = ["GARAN", "THYAO", "NEWCO"], 1500
    harness.redis = FakeRedis(attempted=["NEWCO"])

    result = await jobs._backfill_short_price_histories(TODAY)

    assert harness.calls == [(["GARAN", "THYAO"], TODAY - timedelta(days=3 * 365))]
    assert result == {"tickers": 2, "rows_upserted": 1500, "failed": 0}
    values = harness.redis.values
    assert values["prices:backfill:attempted:GARAN"] == "1"
    assert values["signals:backfill:refresh_until:v3"] == "2026-10-16"
    assert "signals:backfill:attempted:v3" not in values


async def test_recently_attempted_tickers_are_not_fetched_again(harness):
    harness.short = ["NEWCO"]
    harness.redis = FakeRedis(attempted=["NEWCO"])

    assert await jobs._backfill_short_price_histories(TODAY) == {"tickers": 0, "waiting": 1}
    assert harness.calls == []


async def test_no_new_rows_does_not_trigger_signal_refresh(harness):
    harness.short, harness.rows = ["NEWCO"], 0

    await jobs._backfill_short_price_histories(TODAY)

    assert "signals:backfill:refresh_until:v3" not in harness.redis.values
