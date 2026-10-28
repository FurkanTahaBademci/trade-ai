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


async def test_smart_news_uses_fixed_reference_time_and_recent_window():
    from datetime import UTC, datetime, timedelta

    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    db.execute.return_value = result
    ref = datetime(2026, 10, 16, 9, 30, tzinfo=UTC)

    await list_news(db=db, mode="smart", offset=12, ref=ref, limit=12)

    compiled = db.execute.await_args.args[0].compile(dialect=postgresql.dialect())
    values = list(compiled.params.values())
    # Siralama "simdi" yerine sayfalar arasi sabit referansla hesaplanir...
    assert "now()" not in str(compiled).lower()
    assert ref in values
    # ...ve yalniz son 30 gunun haberleri puanlanir.
    assert ref - timedelta(days=30) in values
    assert 12 in values


async def test_ticker_filter_includes_news_linked_by_llm():
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    db.execute.return_value = result

    await list_news(db=db, ticker="thyao", mode="chronological", limit=8)

    compiled = db.execute.await_args.args[0].compile(dialect=postgresql.dialect())
    sql = str(compiled)
    # Kaynak etiketi VEYA basarili LLM degerlendirmesinin hisse listesi eslesir.
    assert "CAST(news_article.ticker_codes AS JSONB) @>" in sql
    assert "OR news_article.id IN (SELECT llm_evaluation.source_id" in sql
    assert "CAST(llm_evaluation.ticker_codes AS JSONB) @>" in sql
    assert ["THYAO"] in compiled.params.values()
    assert "succeeded" in compiled.params.values()


async def test_listed_news_carry_tickers_linked_by_llm():
    from datetime import UTC, datetime
    from types import SimpleNamespace

    article = SimpleNamespace(
        id=7,
        source="foreks",
        canonical_url="https://example.com/haber",
        title="Petrol fiyatlari yukseldi",
        summary=None,
        author=None,
        image_url=None,
        published_at=datetime(2026, 10, 28, 7, 0, tzinfo=UTC),
        ticker_codes=["TUPRS"],
    )
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = [(article, 60, -0.4, "macro", ["THYAO", "TUPRS", "PGSUS"])]
    db.execute.return_value = result

    rows = await list_news(db=db, ticker="THYAO", mode="chronological", limit=8)

    # Kaynak etiketi onde kalir, LLM'in ekledikleri tekrarsiz arkaya gelir.
    assert rows[0].ticker_codes == ["TUPRS", "THYAO", "PGSUS"]
