"""Haber akisi cursor sayfalama regresyon testleri."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import postgresql

from app.api.routers.news import list_news


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
