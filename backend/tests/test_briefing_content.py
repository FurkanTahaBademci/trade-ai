"""Missing evidence and negative sentiment must not become bullish claims."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import RedisError
from sqlalchemy.dialects import postgresql

from app.api.routers import briefing


class FakeSession:
    def __init__(self, *, evaluations=(), signals=(), macro=None):
        self.rows = [list(evaluations), [], [macro] if macro else [], list(signals)]
        self.queries = []

    async def scalars(self, statement):
        self.queries.append(str(statement.compile(dialect=postgresql.dialect())))
        rows = self.rows.pop(0)
        return SimpleNamespace(all=lambda: rows, first=lambda: rows[0] if rows else None)


@pytest.fixture
def redis(monkeypatch):
    client = SimpleNamespace(get=AsyncMock(return_value=None), setex=AsyncMock())
    monkeypatch.setattr(briefing, "get_redis", lambda: client)
    return client


async def test_empty_briefing_does_not_invent_rates_or_sector_facts(redis):
    db = FakeSession()
    result = await briefing.get_market_briefing(db)
    assert "%50" not in result["summary"]
    assert "verisi bulunmuyor" in result["summary"]
    assert result["market_mood"] == "NEUTRAL"
    assert result["sector_commentary"] == []
    assert result["catalysts"] == []
    assert "llm_evaluation.status =" in db.queries[0]
    assert "llm_evaluation.completed_at >=" in db.queries[0]
    assert "news_article.published_at >=" in db.queries[1]
    assert "composite_signal_snapshot.computed_at >=" in db.queries[3]


async def test_high_impact_negative_event_and_weak_signals_stay_negative(redis):
    event = SimpleNamespace(
        impact_score=95,
        sentiment_score=-0.8,
        event_type="earnings",
        ticker_codes=["THYAO"],
        summary="Negatif sonuç",
    )
    signals = [
        SimpleNamespace(ticker=t, composite_score=25, confidence=0.8)
        for t in ("THYAO", "ASELS", "TUPRS")
    ]
    result = await briefing.get_market_briefing(FakeSession(evaluations=[event], signals=signals))
    assert result["catalysts"][0]["impact"] == "NEGATIVE"
    assert result["market_mood"] == "BEARISH"


async def test_low_confidence_scores_do_not_produce_bullish_mood(redis):
    signals = [SimpleNamespace(ticker="THYAO", composite_score=90, confidence=0.1)]
    result = await briefing.get_market_briefing(FakeSession(signals=signals))
    assert result["market_mood"] == "NEUTRAL"


async def test_zero_rate_is_real_data_and_cache_outage_is_tolerated(redis):
    redis.get.side_effect = RedisError("offline")
    redis.setex.side_effect = RedisError("offline")
    macro = SimpleNamespace(policy_rate=0, decision_date=date(2026, 9, 1))
    result = await briefing.get_market_briefing(FakeSession(macro=macro))
    assert "%0.00" in result["summary"]
    assert "2026-09-01" in result["summary"]


async def test_session_and_date_use_istanbul_time(redis, monkeypatch):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 27, 15, 30, tzinfo=UTC)

    monkeypatch.setattr(briefing, "datetime", FrozenDatetime)
    result = await briefing.get_market_briefing(FakeSession())
    assert result["session"] == "AKŞAM"
