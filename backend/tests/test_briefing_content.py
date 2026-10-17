"""Missing evidence and negative sentiment must not become bullish claims."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import RedisError
from sqlalchemy.dialects import postgresql

from app.api.routers import briefing


class FakeSession:
    """Sorgu sirasi: KAP adaylari, haber adaylari (execute), faiz, sinyaller (scalars)."""

    def __init__(self, *, kap=(), news=(), signals=(), macro=None):
        self.rows = [list(kap), list(news), [macro] if macro else [], list(signals)]
        self.queries = []

    def _next(self, statement):
        self.queries.append(str(statement.compile(dialect=postgresql.dialect())))
        rows = self.rows.pop(0) if self.rows else []
        return SimpleNamespace(all=lambda: rows, first=lambda: rows[0] if rows else None)

    async def scalars(self, statement):
        return self._next(statement)

    async def execute(self, statement):
        return self._next(statement)


NOW = datetime.now(UTC)


def evaluation(id=1, *, source_id=10, impact=60, sentiment=0.0, event="earnings", **extra):
    return SimpleNamespace(
        id=id,
        source_id=source_id,
        impact_score=impact,
        sentiment_score=sentiment,
        event_type=event,
        ticker_codes=extra.pop("tickers", ["THYAO"]),
        summary=extra.pop("summary", "LLM özeti"),
        **extra,
    )


def kap_row(ev, *, subject="Finansal rapor", hours_ago=1):
    return (ev, subject, "Özel Durum Açıklaması", NOW - timedelta(hours=hours_ago))


def news_row(ev, *, title="Haber başlığı", summary="Haber özeti", hours_ago=1):
    return (ev, title, summary, NOW - timedelta(hours=hours_ago))


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
    assert result["mood_sample_size"] == 0
    assert "llm_evaluation.status =" in db.queries[0]
    assert "llm_evaluation.completed_at >=" in db.queries[0]
    assert "llm_evaluation.impact_score >=" in db.queries[0]
    assert "DISTINCT ON (llm_evaluation.source_id)" in db.queries[0]
    assert "kap_disclosure.published_at >=" in db.queries[0]
    assert "news_article.published_at >=" in db.queries[1]
    assert "composite_signal_snapshot.computed_at >=" in db.queries[3]
    assert "etki puanı 30 ve üzeri" in result["summary"]


async def test_high_impact_negative_event_and_weak_signals_stay_negative(redis):
    event = evaluation(impact=95, sentiment=-0.8, summary="Negatif sonuç")
    signals = [
        SimpleNamespace(ticker=t, composite_score=25, confidence=0.8)
        for t in ("THYAO", "ASELS", "TUPRS")
    ]
    result = await briefing.get_market_briefing(FakeSession(kap=[kap_row(event)], signals=signals))
    assert result["catalysts"][0]["impact"] == "NEGATIVE"
    assert result["market_mood"] == "BEARISH"
    assert result["mood_sample_size"] == 3


async def test_low_confidence_scores_do_not_produce_bullish_mood(redis):
    signals = [SimpleNamespace(ticker="THYAO", composite_score=90, confidence=0.1)]
    result = await briefing.get_market_briefing(FakeSession(signals=signals))
    assert result["market_mood"] == "NEUTRAL"


async def test_zero_rate_is_real_data_and_cache_outage_is_tolerated(redis):
    redis.get.side_effect = RedisError("offline")
    redis.setex.side_effect = RedisError("offline")
    macro = SimpleNamespace(policy_rate=0, decision_date=date(2026, 9, 1))
    result = await briefing.get_market_briefing(FakeSession(macro=macro))
    assert "politika faizi %0 (01.09.2026)" in result["summary"]


def test_policy_rate_uses_turkish_number_format():
    assert briefing._turkish_rate(37) == "37"
    assert briefing._turkish_rate(37.5) == "37,5"
    assert briefing._turkish_rate(35.25) == "35,25"


async def test_session_and_date_use_istanbul_time(redis, monkeypatch):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 27, 15, 30, tzinfo=UTC)

    monkeypatch.setattr(briefing, "datetime", FrozenDatetime)
    result = await briefing.get_market_briefing(FakeSession())
    assert result["session"] == "AKŞAM"


async def test_catalysts_rank_by_impact_and_recency_not_date(redis):
    fresh_minor = evaluation(1, source_id=1, impact=35, event="other")
    older_major = evaluation(2, source_id=2, impact=85, event="governance", sentiment=0.6)
    kap_major = evaluation(3, source_id=777, impact=70, event="legal", sentiment=-0.4)
    db = FakeSession(
        kap=[kap_row(kap_major, subject="Dava açıldı", hours_ago=2)],
        news=[
            news_row(fresh_minor, title="Okullar tatil mi", hours_ago=0),
            news_row(older_major, title="Yönetim değişti", hours_ago=10),
        ],
    )
    result = await briefing.get_market_briefing(db)
    titles = [item["title"] for item in result["catalysts"]]
    assert titles == ["Yönetim değişti", "Dava açıldı", "Okullar tatil mi"]
    first, second, _ = result["catalysts"]
    assert first["event_label"] == "Yönetim"
    assert first["impact"] == "POSITIVE"
    assert first["description"] == "LLM özeti"
    assert first["href"] == "/haberler/2"
    assert second["event_label"] == "Hukuk"
    assert second["category"] == "KAP"
    assert second["impact"] == "NEGATIVE"
    assert second["href"] == "/kap/777"
    assert "Öne çıkan gelişme: Yönetim değişti (THYAO)." in result["summary"]
    assert not any("kaynaklı piyasa haberi" in item["description"] for item in result["catalysts"])


async def test_news_without_llm_summary_falls_back_to_article_text(redis):
    ev = evaluation(summary=None, sentiment=0.05)
    db = FakeSession(news=[news_row(ev, summary="x" * 300)])
    item = (await briefing.get_market_briefing(db))["catalysts"][0]
    assert item["impact"] == "NEUTRAL"
    assert len(item["description"]) == 238
    assert item["description"].endswith("…")


def test_event_labels_are_turkish_for_every_llm_event_type():
    from typing import get_args

    from app.schemas.llm import EventType

    for value in get_args(EventType):
        assert briefing.event_label(value) != value
    assert briefing.event_label(None) == "Genel"
    assert briefing.event_label("unknown") == "unknown"


def test_sentiment_direction_has_neutral_deadband():
    assert briefing.sentiment_direction(None) == "NEUTRAL"
    assert briefing.sentiment_direction(0.1) == "NEUTRAL"
    assert briefing.sentiment_direction(0.3) == "POSITIVE"
    assert briefing.sentiment_direction(-0.3) == "NEGATIVE"


async def test_focus_returns_highest_impact_item_or_none():
    quiet = await briefing.get_market_focus(FakeSession())
    assert quiet["item"] is None
    assert quiet["threshold"] == briefing.MIN_CATALYST_IMPACT

    db = FakeSession(
        news=[
            news_row(evaluation(1, source_id=1, impact=40), title="Taze", hours_ago=0),
            news_row(evaluation(2, source_id=2, impact=80), title="Önemli", hours_ago=20),
        ]
    )
    focus = await briefing.get_market_focus(db)
    assert focus["item"]["title"] == "Önemli"
    assert focus["item"]["impact_score"] == 80
    assert "_rank" not in focus["item"]
