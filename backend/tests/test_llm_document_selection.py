"""Tier 1 belge seciminin toplu okuma davranisi (SQLite bellek ici DB, ag yok)."""

from datetime import UTC, datetime, timedelta
from itertools import count

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings
from app.llm.service import (
    BACKLOG_MAX_AGE_DAYS,
    KAP_DOCUMENT_COLUMNS,
    NEWS_DOCUMENT_COLUMNS,
    LlmEvaluationService,
    document_from_kap,
    document_from_news,
    evaluation_key,
)
from app.models import KapDisclosure, LlmEvaluation, NewsArticle

SETTINGS = Settings(
    gemini_model_tier1="flash",
    gemini_model_tier2="pro",
    gemini_api_mode="interactions",
    llm_batch_size=20,
    llm_max_attempts=3,
)
NOW = datetime.now(UTC)


def _news(news_id: int, *, title: str, published_at: datetime, tickers=("THYAO",)):
    return NewsArticle(
        id=news_id,
        source="test",
        canonical_url=f"https://example.com/{news_id}",
        url_hash=f"{news_id:064d}",
        title=title,
        summary="Ozet",
        published_at=published_at,
        ticker_codes=list(tickers),
        raw_entry={"buyuk": "x" * 1_000},
    )


async def _seed(db: AsyncSession, evaluated: int) -> dict[str, int]:
    """`evaluated` adet basarili haber + her durumdan birer ornek."""
    ids = {"retry": 9_001, "exhausted": 9_002, "fresh": 9_003, "off_topic": 9_004, "old": 9_005}
    rows = [
        _news(
            index + 1,
            title=f"THYAO hisse haberi {index}",
            published_at=NOW - timedelta(hours=index + 2),
        )
        for index in range(evaluated)
    ]
    rows += [
        _news(ids["retry"], title="THYAO yeniden dene", published_at=NOW - timedelta(days=3)),
        _news(ids["exhausted"], title="THYAO hakki bitti", published_at=NOW - timedelta(hours=1)),
        _news(ids["fresh"], title="THYAO yeni haber", published_at=NOW - timedelta(minutes=5)),
        _news(ids["off_topic"], title="Futbol maci sonucu", published_at=NOW, tickers=()),
        _news(
            ids["old"],
            title="THYAO eski haber",
            published_at=NOW - timedelta(days=BACKLOG_MAX_AGE_DAYS + 10),
        ),
    ]
    db.add_all(rows)
    db.add(
        KapDisclosure(
            disclosure_index=77,
            published_at=NOW - timedelta(minutes=30),
            kap_title="Test A.S.",
            body_text="Govde",
            body_html="<p>" + "x" * 1_000 + "</p>",
            raw_list_item={},
            raw_detail={"buyuk": "x"},
            ticker_codes=["THYAO"],
        )
    )
    await db.commit()

    # Anahtarlar DB'den okunan degerlerle uretilir (SQLite saat dilimini saklamaz).
    documents = {
        row.id: document_from_news(row, max_chars=1_000)
        for row in (await db.execute(select(*NEWS_DOCUMENT_COLUMNS))).all()
    }
    record_ids = count(1)

    def record(news_id: int, *, status: str, attempts: int) -> LlmEvaluation:
        document = documents[news_id]
        return LlmEvaluation(
            id=next(record_ids),
            evaluation_key=evaluation_key(document, tier=1, model="flash", api_mode="interactions"),
            source_type="news",
            source_id=news_id,
            content_hash=document.content_hash,
            prompt_version="v1",
            tier=1,
            model="flash",
            api_mode="interactions",
            status=status,
            attempt_count=attempts,
            input_document={},
            started_at=NOW - timedelta(hours=1),
            completed_at=NOW - timedelta(hours=1),
            created_at=NOW - timedelta(hours=1),
        )

    db.add_all(record(index + 1, status="succeeded", attempts=1) for index in range(evaluated))
    db.add(record(ids["retry"], status="failed", attempts=1))
    db.add(record(ids["exhausted"], status="failed", attempts=3))
    await db.commit()
    return ids


# En yeni 100 haber (scan_limit) her zaman okunur; eski haber backlog sinirina
# ancak daha yeni >100 haber varken kalir.
@pytest.mark.parametrize("evaluated", [120, 300])
async def test_tier1_documents_returns_only_attemptable_documents_in_few_queries(evaluated):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    statements: list[str] = []
    event.listen(
        engine.sync_engine,
        "before_cursor_execute",
        lambda conn, cursor, statement, *args: statements.append(statement),
    )
    ids_iter = count(10_000)

    def assign_id(mapper, connection, target):
        if target.id is None:
            target.id = next(ids_iter)

    event.listen(LlmEvaluation, "before_insert", assign_id)
    try:
        async with engine.begin() as conn:
            for model in (NewsArticle, KapDisclosure, LlmEvaluation):
                await conn.run_sync(model.__table__.create)
        async with AsyncSession(engine, expire_on_commit=False) as db:
            ids = await _seed(db, evaluated)
            statements.clear()
            documents = await LlmEvaluationService(
                db, gateway=None, settings=SETTINGS
            )._tier1_documents()
            selects = [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]

            selected = [(document.source_type, document.source_id) for document in documents]
            # Basarisiz kayit once, sonra en yeniden eskiye; basarili, hakki biten,
            # piyasa disi ve backlog penceresinden eski haber secilmez.
            assert selected == [("news", ids["retry"]), ("news", ids["fresh"]), ("kap", 77)]
            filtered = (
                (
                    await db.execute(
                        select(LlmEvaluation.source_id).where(LlmEvaluation.status == "filtered")
                    )
                )
                .scalars()
                .all()
            )
            assert filtered == [ids["off_topic"]]
            # Belge sayisindan bagimsiz sabit sayida SELECT; agir kolonlar okunmaz.
            assert len(selects) == 7
            assert not any(
                column in sql
                for sql in selects
                for column in ("raw_entry", "body_html", "raw_detail", "input_document")
            )
            kap_document = document_from_kap(
                (await db.execute(select(*KAP_DOCUMENT_COLUMNS))).one(), max_chars=1_000
            )
            assert documents[-1].content_hash == kap_document.content_hash
    finally:
        event.remove(LlmEvaluation, "before_insert", assign_id)
        await engine.dispose()
