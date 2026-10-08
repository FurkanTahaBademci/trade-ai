"""Haber akıllı sıralama (önem + güncellik) ve filtreleme testleri."""

from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import postgresql

from app.api.routers.news import list_news


async def test_smart_news_ranking_applies_time_decay_and_filters_unimportant():
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    db.execute.return_value = result

    await list_news(
        db=db,
        source=None,
        ticker=None,
        mode="smart",
        min_impact=None,
        offset=0,
        limit=20,
    )

    statement = db.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)

    # Akıllı sıralama: Önem puanı ve zaman fonksiyonu
    assert "latest_eval.impact_score >" in sql or "latest_eval.impact_score >=" in sql
    assert "power" in sql.lower()
    assert "extract" in sql.lower()
    assert 20 in compiled.params.values()


async def test_chronological_news_feed_returns_all_in_order_without_impact_filter():
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    db.execute.return_value = result

    await list_news(
        db=db,
        source="bloomberght",
        ticker=None,
        mode="chronological",
        limit=15,
    )

    statement = db.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)

    # Kronolojik mod: published_at desc sirasi, impact_score filtresi yok
    assert "news_article.published_at DESC" in sql
    assert "latest_eval.impact_score >" not in sql
    assert "bloomberght" in compiled.params.values()
    assert 15 in compiled.params.values()


async def test_smart_news_with_custom_min_impact_and_offset():
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    db.execute.return_value = result

    await list_news(
        db=db,
        mode="smart",
        min_impact=50,
        offset=20,
        limit=10,
    )

    statement = db.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)

    assert "latest_eval.impact_score >=" in sql
    assert 50 in compiled.params.values()
    assert 20 in compiled.params.values()
    assert 10 in compiled.params.values()
