"""Liste akislarinin cursor sayfalama regresyon testleri."""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import postgresql

from app.api.routers.evaluations import list_evaluations
from app.api.routers.kap import list_disclosures
from app.api.routers.news import list_news
from app.api.routers.signals import list_latest_signals


async def test_news_cursor_uses_timestamp_and_id_for_stable_pagination():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result
    cursor = datetime(2026, 9, 8, 12, 30, tzinfo=UTC)

    await list_news(
        db=db,
        source=None,
        ticker=None,
        before=cursor,
        before_id=42,
        limit=12,
    )

    statement = db.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)

    assert "news_article.published_at <" in sql
    assert "news_article.published_at =" in sql
    assert "news_article.id <" in sql
    assert compiled.params["published_at_1"] == cursor
    assert compiled.params["published_at_2"] == cursor
    assert compiled.params["id_1"] == 42
    assert compiled.params["param_1"] == 12


async def test_kap_cursor_uses_timestamp_and_disclosure_index():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.unique.return_value.all.return_value = []
    db.execute.return_value = result
    cursor = datetime(2026, 9, 8, 12, 30, tzinfo=UTC)

    await list_disclosures(
        db=db,
        ticker=None,
        disclosure_class=None,
        before=cursor,
        before_index=1_500_000,
        limit=15,
    )

    statement = db.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "kap_disclosure.published_at <" in sql
    assert "kap_disclosure.published_at =" in sql
    assert "kap_disclosure.disclosure_index <" in sql
    assert cursor in compiled.params.values()
    assert 1_500_000 in compiled.params.values()
    assert 15 in compiled.params.values()


async def test_evaluation_cursor_uses_timestamp_and_id():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result
    cursor = datetime(2026, 9, 8, 12, 30, tzinfo=UTC)

    await list_evaluations(
        db=db,
        source_type=None,
        source_id=None,
        ticker=None,
        tier=None,
        status=None,
        before=cursor,
        before_id=81,
        limit=12,
    )

    statement = db.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "llm_evaluation.created_at <" in sql
    assert "llm_evaluation.created_at =" in sql
    assert "llm_evaluation.id <" in sql
    assert cursor in compiled.params.values()
    assert 81 in compiled.params.values()
    assert 12 in compiled.params.values()


async def test_signal_cursor_follows_score_and_ticker_order():
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    db.scalars.return_value = result
    cursor_score = Decimal("75.50")

    await list_latest_signals(
        db=db,
        as_of=date(2026, 9, 8),
        ticker=None,
        label=None,
        min_score=None,
        after_score=cursor_score,
        after_ticker="THYAO",
        after_id=99,
        limit=15,
    )

    statement = db.scalars.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "composite_signal_snapshot.composite_score <" in sql
    assert "composite_signal_snapshot.composite_score =" in sql
    assert "composite_signal_snapshot.ticker >" in sql
    assert "composite_signal_snapshot.id <" in sql
    assert cursor_score in compiled.params.values()
    assert "THYAO" in compiled.params.values()
    assert 99 in compiled.params.values()
    assert 15 in compiled.params.values()
