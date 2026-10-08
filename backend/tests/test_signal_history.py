"""Skor gecmisi endpoint'i ve 'neden bu skor?' yardimcilari (ag/DB yok)."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from redis.exceptions import RedisError

from app.api.routers.signals import signal_score_history
from app.signals.history import (
    evaluation_driver,
    evaluation_effect,
    rank_drivers,
    recommendation_driver,
)


def _evaluation(**kw):
    base = {
        "source_type": "news", "source_id": 7, "summary": "Ozet", "event_type": "earnings",
        "sentiment_score": 0.5, "impact_score": 80, "relevance_score": 90,
        "completed_at": datetime(2026, 9, 1, tzinfo=UTC),
        "created_at": datetime(2026, 9, 1, tzinfo=UTC),
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_effect_is_signed_and_links_to_detail_pages():
    assert evaluation_effect(_evaluation()) == 36.0
    negative = _evaluation(sentiment_score=-1, impact_score=100, relevance_score=100)
    assert evaluation_effect(negative) == -100.0
    assert evaluation_driver(_evaluation())["href"] == "/haberler/7"
    kap = evaluation_driver(_evaluation(source_type="kap", source_id=1500000))
    assert kap["kind"] == "kap" and kap["href"] == "/kap/1500000"


def test_rank_drivers_keeps_strongest_then_orders_newest_first():
    items = [
        {"kind": "news", "title": "a", "occurred_at": "2026-09-01", "effect": 5.0, "href": "/a"},
        {"kind": "news", "title": "b", "occurred_at": "2026-09-03", "effect": -50.0, "href": "/b"},
        {"kind": "news", "title": "c", "occurred_at": "2026-09-02", "effect": 30.0, "href": "/c"},
    ]
    assert [i["title"] for i in rank_drivers(items, limit=2)] == ["b", "c"]


def test_recommendation_driver_without_upside_uses_label():
    row = SimpleNamespace(
        institution="X Yatirim", recommendation_raw="AL", recommendation_normalized="BUY",
        target_price=12.5, upside_pct=None, recommendation_date=date(2026, 9, 2),
    )
    driver = recommendation_driver(row, "THYAO")
    assert driver["effect"] == 30.0 and driver["href"] == "/piyasalar/THYAO#gorusler"


async def test_history_endpoint_is_offline_and_orders_oldest_first():
    redis = AsyncMock()
    redis.get.side_effect = RedisError("down")
    redis.setex.side_effect = RedisError("down")
    rows = [
        SimpleNamespace(as_of_date=date(2026, 9, 2), composite_score=61, signal_label="POSITIVE",
                        confidence=0.7, component_scores={"llm": 70.0}),
        SimpleNamespace(as_of_date=date(2026, 9, 1), composite_score=48, signal_label="NEUTRAL",
                        confidence=0.6, component_scores={"llm": 50.0}),
    ]
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = rows
    db.execute.return_value = result
    db.scalar.return_value = {}
    with patch("app.api.routers.signals.get_redis", return_value=redis):
        out = await signal_score_history("thyao", db=db, start=None, end=None, limit=30)
    assert out.ticker == "THYAO"
    assert [p.as_of_date.isoformat() for p in out.points] == ["2026-09-01", "2026-09-02"]
    assert out.drivers == []
    sql = str(db.execute.await_args_list[0].args[0])
    assert "evidence" not in sql


async def test_history_endpoint_empty_state():
    redis = AsyncMock()
    redis.get.return_value = None
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    db.execute.return_value = result
    with patch("app.api.routers.signals.get_redis", return_value=redis):
        out = await signal_score_history("XXXX", db=db, start=None, end=None, limit=30)
    assert out.points == [] and out.drivers == []
    db.scalar.assert_not_called()
