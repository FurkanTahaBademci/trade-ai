"""Endeks gecmisi eksikse tek seferlik doldurma ve skor gecmisi yenileme isareti (ag/DB yok)."""

from contextlib import asynccontextmanager
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.collectors import index_prices
from app.tasks import jobs


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {"signals:backfill:attempted:v3": "x"}

    async def set(self, key, value):
        self.values[key] = value

    async def delete(self, key):
        self.values.pop(key, None)


@pytest.fixture
def harness(monkeypatch):
    state = SimpleNamespace(rows=0, first_day=None, upserted=0, start_dates=[], redis=FakeRedis())

    class Session:
        async def execute(self, _stmt):
            return SimpleNamespace(one=lambda: (state.rows, state.first_day))

    @asynccontextmanager
    async def session_factory():
        yield Session()

    class Collector:
        def __init__(self, session, start_date=None):
            state.start_dates.append(start_date)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def run_tracked(self):
            return {"rows_upserted": state.upserted}

    monkeypatch.setattr(jobs, "session_factory", session_factory)
    monkeypatch.setattr(jobs, "get_redis", lambda: state.redis)
    monkeypatch.setattr(index_prices, "IndexPriceCollector", Collector)
    return state


async def test_short_index_history_is_backfilled_and_marks_signal_days_for_refresh(harness):
    harness.rows, harness.first_day, harness.upserted = 30, date(2026, 9, 3), 784

    result = await jobs.collect_index_prices({})

    # Varsayilan (3 yil) baslangic icin start_date verilmez.
    assert harness.start_dates == [None]
    assert result["signal_refresh_until"] == "2026-12-12"
    assert harness.redis.values == {"signals:backfill:refresh_until:v3": "2026-12-12"}


async def test_full_index_history_only_refreshes_last_days(harness):
    harness.rows, harness.first_day, harness.upserted = 800, date(2023, 10, 16), 5

    result = await jobs.collect_index_prices({})

    (start,) = harness.start_dates
    assert start is not None and start >= date.today() - timedelta(days=6)
    assert "signal_refresh_until" not in result
    assert harness.redis.values == {"signals:backfill:attempted:v3": "x"}


async def test_fresh_install_backfills_without_refreshing_signals(harness):
    harness.rows, harness.first_day, harness.upserted = 0, None, 784

    result = await jobs.collect_index_prices({})

    assert harness.start_dates == [None]
    assert "signal_refresh_until" not in result
