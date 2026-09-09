"""Operasyon raporlari (depolama ve LLM analiz hatti).

`/sistem` ekraninda buyuyen tablolari (orn. `kap_attachment`) ve Gemini
analiz hattinin gunluk butce/kuyruk durumunu takip etmek icin. Kimlik
dogrulama gerektirmez — `/health/detailed` gibi operasyonel, hassas olmayan
bilgidir. API anahtari veya kaynak metinleri kesinlikle donmez.
"""

from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import Settings
from app.core.db import get_db
from app.core.dynamic_settings import resolve_settings
from app.llm.service import PROMPT_VERSION
from app.models import KapDisclosure, LlmEvaluation, NewsArticle

router = APIRouter(prefix="/api/system", tags=["system"])


def _estimated_requests(document_count: int, group_size: int) -> int:
    return ceil(document_count / max(1, group_size))


def _model_filter(settings: Settings):
    return or_(
        and_(LlmEvaluation.tier == 1, LlmEvaluation.model == settings.gemini_model_tier1),
        and_(LlmEvaluation.tier == 2, LlmEvaluation.model == settings.gemini_model_tier2),
    )


@router.get("/llm")
async def get_llm_report(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    """Gemini hattinin butce, sonuc ve guncel kuyruk ozetini dondurur."""

    settings = await resolve_settings()
    now = datetime.now(UTC)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    usage = (
        await db.execute(
            select(
                func.coalesce(func.sum(LlmEvaluation.input_tokens), 0),
                func.coalesce(func.sum(LlmEvaluation.output_tokens), 0),
                func.max(LlmEvaluation.completed_at),
            ).where(
                LlmEvaluation.status == "succeeded",
                LlmEvaluation.completed_at >= midnight,
            )
        )
    ).one()
    status_rows = await db.execute(
        select(LlmEvaluation.status, func.count(LlmEvaluation.id))
        .where(LlmEvaluation.created_at >= midnight)
        .group_by(LlmEvaluation.status)
    )
    today_counts = {status: int(count) for status, count in status_rows}

    tier1_evaluation = aliased(LlmEvaluation)
    news_evaluated = (
        select(tier1_evaluation.id)
        .where(
            tier1_evaluation.source_type == "news",
            tier1_evaluation.source_id == NewsArticle.id,
            tier1_evaluation.tier == 1,
            tier1_evaluation.prompt_version == PROMPT_VERSION,
            tier1_evaluation.model == settings.gemini_model_tier1,
            tier1_evaluation.api_mode == settings.gemini_api_mode,
        )
        .exists()
    )
    kap_evaluated = (
        select(tier1_evaluation.id)
        .where(
            tier1_evaluation.source_type == "kap",
            tier1_evaluation.source_id == KapDisclosure.disclosure_index,
            tier1_evaluation.tier == 1,
            tier1_evaluation.prompt_version == PROMPT_VERSION,
            tier1_evaluation.model == settings.gemini_model_tier1,
            tier1_evaluation.api_mode == settings.gemini_api_mode,
        )
        .exists()
    )
    pending_news = int(
        await db.scalar(select(func.count(NewsArticle.id)).where(~news_evaluated)) or 0
    )
    pending_kap = int(
        await db.scalar(select(func.count(KapDisclosure.disclosure_index)).where(~kap_evaluated))
        or 0
    )

    succeeded_later = aliased(LlmEvaluation)
    resolved_failure = (
        select(succeeded_later.id)
        .where(
            succeeded_later.source_type == LlmEvaluation.source_type,
            succeeded_later.source_id == LlmEvaluation.source_id,
            succeeded_later.tier == LlmEvaluation.tier,
            succeeded_later.prompt_version == LlmEvaluation.prompt_version,
            succeeded_later.api_mode == LlmEvaluation.api_mode,
            succeeded_later.model == LlmEvaluation.model,
            succeeded_later.status == "succeeded",
            succeeded_later.created_at > LlmEvaluation.created_at,
        )
        .exists()
    )
    current_evaluations = and_(
        LlmEvaluation.prompt_version == PROMPT_VERSION,
        LlmEvaluation.api_mode == settings.gemini_api_mode,
        _model_filter(settings),
    )
    unresolved_failures = int(
        await db.scalar(
            select(func.count(LlmEvaluation.id)).where(
                current_evaluations,
                LlmEvaluation.status == "failed",
                ~resolved_failure,
            )
        )
        or 0
    )
    retryable_failures = int(
        await db.scalar(
            select(func.count(LlmEvaluation.id)).where(
                current_evaluations,
                LlmEvaluation.status == "failed",
                LlmEvaluation.attempt_count < settings.llm_max_attempts,
                ~resolved_failure,
            )
        )
        or 0
    )
    stale_running = int(
        await db.scalar(
            select(func.count(LlmEvaluation.id)).where(
                current_evaluations,
                LlmEvaluation.status == "running",
                LlmEvaluation.started_at < now - timedelta(minutes=30),
            )
        )
        or 0
    )

    input_used, output_used = int(usage[0]), int(usage[1])
    pending_documents = pending_news + pending_kap
    return {
        "generated_at": now,
        "config": {
            "enabled": settings.llm_enabled,
            "api_mode": settings.gemini_api_mode,
            "tier1_model": settings.gemini_model_tier1,
            "tier2_model": settings.gemini_model_tier2,
            "tier1_group_size": settings.llm_tier1_group_size,
            "batch_size": settings.llm_batch_size,
            "max_attempts": settings.llm_max_attempts,
        },
        "budget": {
            "window_started_at": midnight,
            "input_tokens": {
                "used": input_used,
                "limit": settings.llm_daily_input_token_limit,
            },
            "output_tokens": {
                "used": output_used,
                "limit": settings.llm_daily_output_token_limit,
            },
            "exhausted": (
                input_used >= settings.llm_daily_input_token_limit
                or output_used >= settings.llm_daily_output_token_limit
            ),
        },
        "today": {
            "succeeded": today_counts.get("succeeded", 0),
            "failed": today_counts.get("failed", 0),
            "running": today_counts.get("running", 0),
            "last_completed_at": usage[2],
        },
        "backlog": {
            "news": pending_news,
            "kap": pending_kap,
            "documents": pending_documents,
            "estimated_tier1_requests": _estimated_requests(
                pending_documents, settings.llm_tier1_group_size
            ),
            "retryable_failures": retryable_failures,
            "stale_running": stale_running,
        },
        "unresolved_failures": unresolved_failures,
    }


@router.get("/storage")
async def get_storage_report(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    database_size = await db.scalar(text("SELECT pg_database_size(current_database())"))
    result = await db.execute(
        text(
            """
            SELECT relname AS table_name,
                   pg_total_relation_size(relid) AS size_bytes,
                   n_live_tup AS row_estimate
            FROM pg_catalog.pg_stat_user_tables
            ORDER BY size_bytes DESC
            LIMIT 15
            """
        )
    )
    tables = [
        {
            "table": row.table_name,
            "size_bytes": int(row.size_bytes),
            "row_estimate": max(0, int(row.row_estimate)),
        }
        for row in result
    ]
    return {"database_size_bytes": int(database_size or 0), "tables": tables}
