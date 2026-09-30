"""Operasyon raporlari (depolama ve LLM analiz hatti).

`/sistem` ekraninda buyuyen tablolari (orn. `kap_attachment`) ve Gemini
analiz hattinin gunluk butce/kuyruk durumunu takip etmek icin. Kimlik
dogrulama gerektirmez — `/health/detailed` gibi operasyonel, hassas olmayan
bilgidir. API anahtari veya kaynak metinleri kesinlikle donmez.
"""

from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ValidationError
from redis.exceptions import RedisError
from sqlalchemy import and_, case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.api.routers.schedules import require_admin_token
from app.core.config import Settings
from app.core.db import engine, get_db
from app.core.dynamic_settings import resolve_settings
from app.core.redis import get_redis
from app.llm.quota import get_provider_pause
from app.llm.service import PROMPT_VERSION
from app.models import (
    CompositeSignalSnapshot,
    FundSnapshot,
    Instrument,
    KapDisclosure,
    LlmEvaluation,
    NewsArticle,
)

logger = structlog.get_logger("system")

router = APIRouter(prefix="/api/system", tags=["system"])

FAILURE_CATEGORY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("daily_quota", ("requests per day", "daily quota", "per day on free tier")),
    ("rate_limit", ("rate limit", "resource_exhausted", "429")),
    (
        "provider_unavailable",
        ("connection", "high demand", "html", "403", "timeout", "timed out"),
    ),
    ("invalid_response", ("validation", "invalid json", "schema", "structured output")),
)
FAILURE_CATEGORY_LABELS = {
    "daily_quota": "Günlük sağlayıcı kotası",
    "rate_limit": "İstek hız sınırı",
    "provider_unavailable": "Sağlayıcı/bağlantı",
    "invalid_response": "Geçersiz model yanıtı",
    "other": "Diğer",
}


def classify_llm_failure(error_text: str | None) -> str:
    lowered = (error_text or "").lower()
    for category, patterns in FAILURE_CATEGORY_PATTERNS:
        if any(pattern in lowered for pattern in patterns):
            return category
    return "other"


def _failure_category_expression():
    lowered = func.lower(func.coalesce(LlmEvaluation.error_text, ""))
    return case(
        *(
            (or_(*(lowered.contains(pattern) for pattern in patterns)), category)
            for category, patterns in FAILURE_CATEGORY_PATTERNS
        ),
        else_="other",
    )


class SystemStatsOut(BaseModel):
    instruments_total: int
    news_total: int
    news_by_source: dict[str, int]
    disclosures_total: int
    signals_total: int
    signals_by_label: dict[str, int]
    evaluations_total: int
    evaluations_by_source: dict[str, int]
    funds_total: int


@router.get("/stats", response_model=SystemStatsOut)
async def get_system_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SystemStatsOut:
    """Sistem genelindeki varlık toplamlarını ve kategori kırılımlarını döndürür."""
    redis = get_redis()
    cache_key = "system:stats:totals"
    try:
        cached = await redis.get(cache_key)
        if cached:
            return SystemStatsOut.model_validate_json(cached)
    except (RedisError, ValidationError) as exc:
        logger.warning("system_stats_cache_read_failed", error=str(exc))

    instruments_total = int(
        await db.scalar(
            select(func.count(Instrument.ticker)).where(Instrument.is_active.is_(True))
        )
        or 0
    )
    news_total = int(await db.scalar(select(func.count(NewsArticle.id))) or 0)
    news_source_rows = await db.execute(
        select(NewsArticle.source, func.count(NewsArticle.id)).group_by(NewsArticle.source)
    )
    news_by_source = {str(row[0]): int(row[1]) for row in news_source_rows}

    disclosures_total = int(
        await db.scalar(select(func.count(KapDisclosure.disclosure_index))) or 0
    )

    latest_signal_date = await db.scalar(select(func.max(CompositeSignalSnapshot.as_of_date)))
    signals_total = 0
    signals_by_label: dict[str, int] = {}
    if latest_signal_date is not None:
        signals_total = int(
            await db.scalar(
                select(func.count(CompositeSignalSnapshot.id)).where(
                    CompositeSignalSnapshot.as_of_date == latest_signal_date
                )
            )
            or 0
        )
        signal_label_rows = await db.execute(
            select(
                CompositeSignalSnapshot.signal_label, func.count(CompositeSignalSnapshot.id)
            )
            .where(CompositeSignalSnapshot.as_of_date == latest_signal_date)
            .group_by(CompositeSignalSnapshot.signal_label)
        )
        signals_by_label = {str(row[0]): int(row[1]) for row in signal_label_rows}

    evaluations_total = int(await db.scalar(select(func.count(LlmEvaluation.id))) or 0)
    evaluation_source_rows = await db.execute(
        select(LlmEvaluation.source_type, func.count(LlmEvaluation.id)).group_by(
            LlmEvaluation.source_type
        )
    )
    evaluations_by_source = {str(row[0]): int(row[1]) for row in evaluation_source_rows}

    funds_total = int(
        await db.scalar(select(func.count(func.distinct(FundSnapshot.fund_code)))) or 0
    )

    stats = SystemStatsOut(
        instruments_total=instruments_total,
        news_total=news_total,
        news_by_source=news_by_source,
        disclosures_total=disclosures_total,
        signals_total=signals_total,
        signals_by_label=signals_by_label,
        evaluations_total=evaluations_total,
        evaluations_by_source=evaluations_by_source,
        funds_total=funds_total,
    )

    try:
        await redis.set(cache_key, stats.model_dump_json(), ex=60)
    except RedisError as exc:
        logger.warning("system_stats_cache_write_failed", error=str(exc))

    return stats


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
    failure_category = _failure_category_expression().label("category")
    failure_category_rows = await db.execute(
        select(failure_category, func.count(LlmEvaluation.id))
        .where(
            current_evaluations,
            LlmEvaluation.status == "failed",
            ~resolved_failure,
        )
        .group_by(failure_category)
    )
    failure_counts = {str(category): int(count) for category, count in failure_category_rows}
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
        "provider_pause": await get_provider_pause(db, settings, now=now),
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
                (
                    settings.llm_daily_input_token_limit > 0
                    and input_used >= settings.llm_daily_input_token_limit
                )
                or (
                    settings.llm_daily_output_token_limit > 0
                    and output_used >= settings.llm_daily_output_token_limit
                )
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
        "failure_categories": [
            {
                "category": category,
                "label": label,
                "count": failure_counts.get(category, 0),
            }
            for category, label in FAILURE_CATEGORY_LABELS.items()
            if failure_counts.get(category, 0) > 0
        ],
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


@router.post("/storage/vacuum")
async def vacuum_storage_endpoint(
    _admin: Annotated[str, Depends(require_admin_token)],
) -> dict:
    """Eski ve silinen binary/TOAST verilerini diskten temizler (VACUUM FULL kap_attachment)."""
    async with engine.connect() as conn:
        autocommit_conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        dialect = engine.dialect.name
        if dialect == "postgresql":
            size_before = int(
                await autocommit_conn.scalar(text("SELECT pg_database_size(current_database())"))
                or 0
            )
            try:
                await autocommit_conn.execute(text("VACUUM FULL kap_attachment"))
            except Exception as exc:  # noqa: BLE001 - tablonun kilitli olmasi veya bulunamamasi vakumlamayi engellemesin
                logger.warning("vacuum_kap_attachment_failed", error=str(exc))
            await autocommit_conn.execute(text("VACUUM ANALYZE"))
            size_after = int(
                await autocommit_conn.scalar(text("SELECT pg_database_size(current_database())"))
                or 0
            )
            freed_bytes = max(0, size_before - size_after)
            freed_mb = freed_bytes / (1024 * 1024)
            return {
                "ok": True,
                "size_before_bytes": size_before,
                "size_after_bytes": size_after,
                "freed_bytes": freed_bytes,
                "message": f"Depolama temizlendi. {freed_mb:.1f} MB disk alanı geri kazanıldı.",
            }
        else:
            await autocommit_conn.execute(text("VACUUM"))
            return {
                "ok": True,
                "message": "Veritabanı başarıyla vakumlandı.",
            }
