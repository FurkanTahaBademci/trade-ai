"""Bilesik skor siralamasi ve ticker gecmisi endpoint'leri."""

import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from redis.exceptions import RedisError
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.csv_export import csv_response
from app.core.db import get_db
from app.core.redis import get_redis
from app.models import (
    AnalystRecommendation,
    CompositeSignalSnapshot,
    IndexDaily,
    LlmEvaluation,
    PriceDaily,
)
from app.schemas.signal import (
    CompositeSignalOut,
    SignalHistoryOut,
    SignalHorizonStatOut,
)
from app.signals.accuracy import (
    DEFAULT_HORIZONS,
    PricePoint,
    SignalObservation,
    compute_signal_accuracy,
)
from app.signals.history import evaluation_driver, rank_drivers, recommendation_driver
from app.signals.service import MODEL_VERSION

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/signals", tags=["signals"])
BENCHMARK_INDEX = "XU100"


class SignalLabel(StrEnum):
    VERY_POSITIVE = "VERY_POSITIVE"
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"
    VERY_NEGATIVE = "VERY_NEGATIVE"


@router.get("", response_model=list[CompositeSignalOut])
async def list_latest_signals(
    db: Annotated[AsyncSession, Depends(get_db)],
    as_of: Annotated[date | None, Query()] = None,
    ticker: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
    label: Annotated[SignalLabel | None, Query()] = None,
    min_score: Annotated[float | None, Query(ge=0, le=100)] = None,
    after_score: Annotated[Decimal | None, Query(ge=0, le=100)] = None,
    after_ticker: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
    after_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[CompositeSignalSnapshot]:
    target_date = as_of or await db.scalar(
        select(func.max(CompositeSignalSnapshot.as_of_date)).where(
            CompositeSignalSnapshot.model_version == MODEL_VERSION
        )
    )
    if target_date is None:
        return []
    stmt = select(CompositeSignalSnapshot).where(
        CompositeSignalSnapshot.as_of_date == target_date,
        CompositeSignalSnapshot.model_version == MODEL_VERSION,
    )
    if ticker:
        stmt = stmt.where(CompositeSignalSnapshot.ticker == ticker.upper())
    if label:
        stmt = stmt.where(CompositeSignalSnapshot.signal_label == label)
    if min_score is not None:
        stmt = stmt.where(CompositeSignalSnapshot.composite_score >= min_score)
    if after_score is not None and after_ticker and after_id:
        stmt = stmt.where(
            or_(
                CompositeSignalSnapshot.composite_score < after_score,
                and_(
                    CompositeSignalSnapshot.composite_score == after_score,
                    CompositeSignalSnapshot.ticker > after_ticker.upper(),
                ),
                and_(
                    CompositeSignalSnapshot.composite_score == after_score,
                    CompositeSignalSnapshot.ticker == after_ticker.upper(),
                    CompositeSignalSnapshot.id < after_id,
                ),
            )
        )
    elif after_score is not None and after_ticker:
        stmt = stmt.where(
            or_(
                CompositeSignalSnapshot.composite_score < after_score,
                and_(
                    CompositeSignalSnapshot.composite_score == after_score,
                    CompositeSignalSnapshot.ticker > after_ticker.upper(),
                ),
            )
        )
    stmt = stmt.order_by(
        CompositeSignalSnapshot.composite_score.desc(),
        CompositeSignalSnapshot.ticker,
        CompositeSignalSnapshot.id.desc(),
    ).limit(limit)
    return list((await db.scalars(stmt)).all())


@router.get("/accuracy", response_model=list[SignalHorizonStatOut])
async def signal_accuracy_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    model_version: Annotated[str, Query()] = MODEL_VERSION,
) -> list[SignalHorizonStatOut]:
    """Gecmis sinyallerin gercek ileri getirisiyle karsilastirilmasi.

    Not: bu bir /{ticker} yol parametresi degildir — literal "/accuracy"
    segmenti oldugundan asagidaki /{ticker} route'undan ONCE tanimlanmali,
    aksi halde "accuracy" bir ticker kodu sanilip yakalanir.
    """
    cache_key = f"signals:accuracy:v2:{model_version}"
    redis = get_redis()
    try:
        cached = await redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            return [SignalHorizonStatOut.model_validate(item) for item in data]
    except (RedisError, json.JSONDecodeError, TypeError) as exc:
        logger.debug("Redis cache miss or read error: %s", exc)

    signal_rows = (
        await db.execute(
            select(
                CompositeSignalSnapshot.ticker,
                CompositeSignalSnapshot.as_of_date,
                CompositeSignalSnapshot.composite_score,
                CompositeSignalSnapshot.signal_label,
            ).where(CompositeSignalSnapshot.model_version == model_version)
        )
    ).all()
    tickers = {row.ticker for row in signal_rows}
    price_points: list[PricePoint] = []
    # Ilk sinyalden onceki fiyatlar hesaba girmez; yillarca geriye giden tum
    # fiyat gecmisini cekmek soguk onbellekte istegi saniyelerce uzatiyordu.
    first_signal = min((row.as_of_date for row in signal_rows), default=None)
    if tickers:
        price_stmt = (
            select(PriceDaily.ticker, PriceDaily.date, PriceDaily.close)
            .where(PriceDaily.ticker.in_(tickers), PriceDaily.date >= first_signal)
            .order_by(PriceDaily.ticker, PriceDaily.date)
        )
        price_rows = (await db.execute(price_stmt)).all()
        price_points = [PricePoint(row.ticker, row.date, row.close) for row in price_rows]
    benchmark_rows = (
        await db.execute(
            select(IndexDaily.date, IndexDaily.value)
            .where(
                IndexDaily.index_code == BENCHMARK_INDEX,
                IndexDaily.date >= (first_signal or date.min),
            )
            .order_by(IndexDaily.date)
        )
    ).all()

    stats = compute_signal_accuracy(
        [
            SignalObservation(row.ticker, row.as_of_date, row.composite_score, row.signal_label)
            for row in signal_rows
        ],
        price_points,
        horizons=DEFAULT_HORIZONS,
        benchmark=[(row.date, row.value) for row in benchmark_rows],
    )
    validated = [SignalHorizonStatOut.model_validate(item) for item in stats]
    try:
        # Ileri getiriler gun sonu fiyatiyla degisir; saatlik tazelik yeterli.
        await redis.setex(
            cache_key,
            3600,
            json.dumps([item.model_dump(mode="json") for item in validated]),
        )
    except RedisError as exc:
        logger.debug("Redis cache write error: %s", exc)
    return validated


@router.get("/{ticker}/history", response_model=SignalHistoryOut)
async def signal_score_history(
    ticker: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    start: Annotated[date | None, Query()] = None,
    end: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=730)] = 180,
) -> SignalHistoryOut:
    """Skor zaman serisi (evidence JSON'u cekilmez) + son skoru etkileyen kayitlar."""
    code = ticker.upper()
    cache_key = f"signals:history:{MODEL_VERSION}:{code}:{start}:{end}:{limit}"
    redis = get_redis()
    try:
        cached = await redis.get(cache_key)
        if cached:
            return SignalHistoryOut.model_validate(json.loads(cached))
    except (RedisError, json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.debug("Redis cache miss or read error: %s", exc)

    stmt = select(
        CompositeSignalSnapshot.as_of_date,
        CompositeSignalSnapshot.composite_score,
        CompositeSignalSnapshot.signal_label,
        CompositeSignalSnapshot.confidence,
        CompositeSignalSnapshot.component_scores,
    ).where(
        CompositeSignalSnapshot.ticker == code,
        CompositeSignalSnapshot.model_version == MODEL_VERSION,
    )
    if start:
        stmt = stmt.where(CompositeSignalSnapshot.as_of_date >= start)
    if end:
        stmt = stmt.where(CompositeSignalSnapshot.as_of_date <= end)
    rows = list(
        (await db.execute(stmt.order_by(CompositeSignalSnapshot.as_of_date.desc()).limit(limit))).all()
    )
    rows.reverse()

    drivers: list[dict] = []
    if rows:
        latest_date = rows[-1].as_of_date
        evidence = await db.scalar(
            select(CompositeSignalSnapshot.evidence).where(
                CompositeSignalSnapshot.ticker == code,
                CompositeSignalSnapshot.model_version == MODEL_VERSION,
                CompositeSignalSnapshot.as_of_date == latest_date,
            )
        )
        evidence = evidence or {}
        evaluation_ids = (evidence.get("llm") or {}).get("evaluation_ids") or []
        if evaluation_ids:
            evaluations = (
                await db.execute(
                    select(
                        LlmEvaluation.source_type,
                        LlmEvaluation.source_id,
                        LlmEvaluation.summary,
                        LlmEvaluation.event_type,
                        LlmEvaluation.sentiment_score,
                        LlmEvaluation.impact_score,
                        LlmEvaluation.relevance_score,
                        LlmEvaluation.completed_at,
                        LlmEvaluation.created_at,
                    ).where(LlmEvaluation.id.in_(evaluation_ids[:200]))
                )
            ).all()
            drivers.extend(evaluation_driver(row) for row in evaluations)
        if "analyst" in evidence:
            recommendations = (
                await db.execute(
                    select(
                        AnalystRecommendation.institution,
                        AnalystRecommendation.recommendation_raw,
                        AnalystRecommendation.recommendation_normalized,
                        AnalystRecommendation.target_price,
                        AnalystRecommendation.upside_pct,
                        AnalystRecommendation.recommendation_date,
                    )
                    .where(
                        AnalystRecommendation.ticker == code,
                        AnalystRecommendation.recommendation_date <= latest_date,
                        AnalystRecommendation.recommendation_date
                        >= latest_date - timedelta(days=90),
                    )
                    .order_by(AnalystRecommendation.recommendation_date.desc())
                    .limit(20)
                )
            ).all()
            drivers.extend(recommendation_driver(row, code) for row in recommendations)

    result = SignalHistoryOut.model_validate(
        {
            "ticker": code,
            "points": [
                {
                    "as_of_date": row.as_of_date,
                    "composite_score": row.composite_score,
                    "signal_label": row.signal_label,
                    "confidence": row.confidence,
                    "component_scores": row.component_scores,
                }
                for row in rows
            ],
            "drivers": rank_drivers(drivers),
        }
    )
    try:
        await redis.setex(cache_key, 120, json.dumps(result.model_dump(mode="json")))
    except RedisError as exc:
        logger.debug("Redis cache write error: %s", exc)
    return result


@router.get("/export.csv")
async def export_signals_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    as_of: Annotated[date | None, Query()] = None,
    label: Annotated[SignalLabel | None, Query()] = None,
    min_score: Annotated[float | None, Query(ge=0, le=100)] = None,
    limit: Annotated[int, Query(ge=1, le=1_000)] = 1_000,
):
    rows = await list_latest_signals(
        db=db,
        as_of=as_of,
        ticker=None,
        label=label,
        min_score=min_score,
        after_score=None,
        after_ticker=None,
        after_id=None,
        limit=limit,
    )
    return csv_response(
        f"sinyaller-{rows[0].as_of_date.isoformat() if rows else 'bos'}.csv",
        ["Hisse", "Tarih", "Bileşik skor", "Etiket", "Güven", "Kapsam", "Model", "Hesaplandı"],
        [
            (
                r.ticker,
                r.as_of_date,
                r.composite_score,
                r.signal_label,
                r.confidence,
                r.coverage_count,
                r.model_version,
                r.computed_at,
            )
            for r in rows
        ],
    )


@router.get("/{ticker}", response_model=list[CompositeSignalOut])
async def signal_history(
    ticker: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=365)] = 90,
) -> list[CompositeSignalSnapshot]:
    stmt = (
        select(CompositeSignalSnapshot)
        .where(
            CompositeSignalSnapshot.ticker == ticker.upper(),
            CompositeSignalSnapshot.model_version == MODEL_VERSION,
        )
        .order_by(CompositeSignalSnapshot.as_of_date.desc())
        .limit(limit)
    )
    return list((await db.scalars(stmt)).all())
