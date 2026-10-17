"""Liste uclari yanitta olmayan buyuk sutunlari okumamali (ana sayfa/akis maliyeti)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.routers.evaluations import list_evaluations
from app.api.routers.kap import list_disclosures
from app.api.routers.news import list_news
from app.models import KapAttachment, KapDisclosure, LlmEvaluation
from app.schemas.kap import KapDisclosureListOut
from app.schemas.llm import LlmEvaluationListOut

PUBLISHED = datetime(2026, 10, 17, 9, tzinfo=UTC)


def _selected_columns(sql: str) -> str:
    return sql.split("FROM", 1)[0]


async def test_news_list_does_not_select_raw_entry():
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    db.execute.return_value = result

    await list_news(db=db, mode="smart", ref=PUBLISHED, limit=6)

    sql = str(db.execute.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "news_article.title" in _selected_columns(sql)
    assert "raw_entry" not in _selected_columns(sql)


async def test_kap_and_evaluation_lists_serialize_without_heavy_columns():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            for table in (KapDisclosure.__table__, KapAttachment.__table__, LlmEvaluation.__table__):
                await conn.run_sync(table.create)
        async with AsyncSession(engine) as db:
            db.add(
                KapDisclosure(
                    disclosure_index=1,
                    published_at=PUBLISHED,
                    kap_title="GERCEK A.S.",
                    subject="Özel Durum Açıklaması (Genel)",
                    ticker_codes=["GUBRF"],
                    attachment_count=1,
                    body_html="<p>uzun govde</p>",
                    body_text="uzun govde",
                    raw_list_item={"ham": True},
                    raw_detail={"ham": True},
                    attachments=[
                        KapAttachment(obj_id="abc", file_name="ek.pdf", raw_metadata={})
                    ],
                )
            )
            db.add(
                LlmEvaluation(
                    id=1,
                    evaluation_key="k1",
                    source_type="kap",
                    source_id=1,
                    content_hash="h",
                    prompt_version="v1",
                    tier=1,
                    model="m",
                    status="succeeded",
                    input_document={"text": "x" * 12_000},
                    ticker_codes=["GUBRF"],
                    impact_score=60,
                    summary="ozet",
                    rationale="gerekce",
                    result={"ham": True},
                    raw_response="{}",
                    created_at=PUBLISHED,
                )
            )
            await db.commit()
            db.expunge_all()

            statements = []
            original_execute = db.execute

            async def recording_execute(statement, *args, **kwargs):
                statements.append(str(statement.compile(dialect=postgresql.dialect())))
                return await original_execute(statement, *args, **kwargs)

            db.execute = recording_execute

            disclosures = await list_disclosures(
                db=db, ticker=None, disclosure_class=None, before=None, before_index=None, limit=5
            )
            evaluations = await list_evaluations(db=db, limit=5)

            # Yanit semasi yalniz yuklu alanlari okur; lazy-load denemesi burada patlardi.
            assert [KapDisclosureListOut.model_validate(item).disclosure_index for item in disclosures] == [1]
            assert [LlmEvaluationListOut.model_validate(item).summary for item in evaluations] == ["ozet"]
            kap_columns, evaluation_columns = (_selected_columns(sql) for sql in statements)
            for column in ("body_html", "body_text", "raw_list_item", "raw_detail"):
                assert column not in kap_columns
            for column in ("input_document", "raw_response", "rationale", ".result"):
                assert column not in evaluation_columns
    finally:
        await engine.dispose()
