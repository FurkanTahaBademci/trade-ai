from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings
from app.llm.quota import get_provider_pause, quota_pause
from app.llm.service import (
    GatewayResponse,
    LlmEvaluationService,
    SourceDocument,
    evaluation_key,
)
from app.models import LlmEvaluation

DAILY_ERROR = (
    'event: error\ndata: {"error":{"message":"Rate limit exceeded for model flash '
    '(limit: 500 requests per day on Free Tier). Please retry in 29s",'
    '"code":"rate_limit_exceeded"}}'
)


@pytest.mark.parametrize(("date", "expected"), [
    ("2026-09-28T16:00:00+00:00", "2026-09-29T07:00:00+00:00"),
    ("2026-01-28T16:00:00+00:00", "2026-01-29T08:00:00+00:00"),
    ("2026-03-08T07:30:00+00:00", "2026-03-08T08:00:00+00:00"),
    ("2026-11-01T07:30:00+00:00", "2026-11-02T08:00:00+00:00"),
])
def test_daily_quota_waits_for_pacific_midnight_not_short_retry_hint(date, expected):
    pause = quota_pause(DAILY_ERROR, datetime.fromisoformat(date), "flash")
    assert pause == {"reason": "daily_quota", "model": "flash", "retry_at": expected}


def test_transient_rate_limit_and_nonquota_errors():
    now = datetime(2026, 9, 28, 16, tzinfo=UTC)
    pause = quota_pause("429 RESOURCE_EXHAUSTED. Please retry in 120s", now, "flash")
    assert datetime.fromisoformat(pause["retry_at"]) == now + timedelta(seconds=120)
    assert quota_pause("invalid_request: unknown model", now, "flash") is None
    assert quota_pause("connection reset", now, "flash") is None


async def test_persisted_pause_survives_new_session_expires_and_is_model_scoped():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(LlmEvaluation.__table__.create)
        now = datetime(2026, 9, 28, 16, tzinfo=UTC)
        settings = Settings(gemini_model_tier1="flash", gemini_model_tier2="flash")
        async with AsyncSession(engine) as db:
            db.add(LlmEvaluation(id=1, evaluation_key="a", source_type="news", source_id=1,
                                 content_hash="a", prompt_version="v1", tier=1, model="flash",
                                 status="failed", input_document={}, error_text=DAILY_ERROR,
                                 completed_at=now, attempt_count=0))
            await db.commit()
        async with AsyncSession(engine) as db:
            assert (await get_provider_pause(db, settings, now=now))["reason"] == "daily_quota"
            assert await get_provider_pause(db, settings, now=now + timedelta(days=1)) is None
            other = Settings(gemini_model_tier1="other", gemini_model_tier2="other")
            assert await get_provider_pause(db, other, now=now) is None
            db.add(LlmEvaluation(id=2, evaluation_key="b", source_type="news", source_id=2,
                                 content_hash="b", prompt_version="v1", tier=1, model="flash",
                                 status="succeeded", input_document={},
                                 completed_at=now + timedelta(minutes=1)))
            await db.commit()
            assert await get_provider_pause(db, settings, now=now + timedelta(minutes=2)) is None
    finally:
        await engine.dispose()


@pytest.mark.parametrize("isolate", [False, True])
async def test_quota_stops_batch_and_isolation_without_consuming_document_retries(isolate, monkeypatch):
    documents = [SourceDocument("news", n, datetime.now(UTC), str(n), {}) for n in range(4)]
    settings = Settings(gemini_model_tier1="flash", gemini_model_tier2="flash",
                        llm_tier1_group_size=2)
    gateway = SimpleNamespace(generate=AsyncMock(side_effect=RuntimeError(DAILY_ERROR)))
    if isolate:
        gateway.generate.side_effect = [GatewayResponse(data={"results": []}, raw_text="{}"),
                                        RuntimeError(DAILY_ERROR)]
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    service = LlmEvaluationService(session, gateway, settings=settings)
    records = {}

    async def start(document, **kwargs):
        record = SimpleNamespace(model="flash", attempt_count=1)
        records[kwargs["key"]] = record
        return record

    async def existing(key):
        return records[key]

    service._start_record = start
    service._existing = existing
    monkeypatch.setattr("app.llm.service.get_provider_pause", AsyncMock(return_value=None))
    service._known_tickers = AsyncMock(return_value=set())
    service._daily_usage = AsyncMock(return_value=(0, 0))
    service._reconcile_stale_records = AsyncMock(return_value=0)
    service._tier1_documents = AsyncMock(return_value=documents)
    service._tier2_parents = AsyncMock()
    result = await service.run()
    assert result["tier1_failed"] == 2
    assert len(records) == 2
    service._tier2_parents.assert_not_awaited()
    assert gateway.generate.await_count == (2 if isolate else 1)
    assert service._provider_pause["reason"] == "daily_quota"
    assert all(record.attempt_count == 0 and record.status == "failed" for record in records.values())
    assert all("requests per day" in record.error_text for record in records.values())
    assert evaluation_key(documents[2], tier=1, model="flash") not in records


async def test_run_skips_all_work_during_persisted_pause(monkeypatch):
    pause = quota_pause(DAILY_ERROR, datetime.now(UTC), "flash")
    monkeypatch.setattr("app.llm.service.get_provider_pause", AsyncMock(return_value=pause))
    gateway = SimpleNamespace(generate=AsyncMock())
    service = LlmEvaluationService(SimpleNamespace(), gateway)
    service._known_tickers = AsyncMock(return_value=set())
    service._daily_usage = AsyncMock(return_value=(100, 50))
    service._reconcile_stale_records = AsyncMock(return_value=0)
    service._tier1_documents = AsyncMock()
    service._tier2_parents = AsyncMock()
    result = await service.run()
    assert result["provider_pause"] == pause
    assert result["tier1_failed"] == 0
    service._tier1_documents.assert_not_awaited()
    service._tier2_parents.assert_not_awaited()
    gateway.generate.assert_not_awaited()


async def test_stale_running_records_are_reconciled_before_retry_selection():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(LlmEvaluation.__table__.create)
        now = datetime.now(UTC)
        settings = Settings(gemini_model_tier1="flash", gemini_model_tier2="pro")
        async with AsyncSession(engine) as db:
            db.add_all([
                LlmEvaluation(id=1, evaluation_key="stale", source_type="news", source_id=1,
                              content_hash="a", prompt_version="v1", tier=1, model="flash",
                              status="running", input_document={}, attempt_count=3,
                              started_at=now - timedelta(minutes=31)),
                LlmEvaluation(id=2, evaluation_key="fresh", source_type="news", source_id=2,
                              content_hash="b", prompt_version="v1", tier=1, model="flash",
                              status="running", input_document={}, attempt_count=1,
                              started_at=now - timedelta(minutes=5)),
            ])
            await db.commit()
            service = LlmEvaluationService(db, SimpleNamespace(), settings=settings)

            assert await service._reconcile_stale_records() == 1
            stale = await db.get(LlmEvaluation, 1)
            fresh = await db.get(LlmEvaluation, 2)
            assert stale.status == "failed"
            assert stale.completed_at is not None
            assert "30 dakika" in stale.error_text
            assert fresh.status == "running"
    finally:
        await engine.dispose()
