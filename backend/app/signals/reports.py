"""Sinyal dogrulugu ve bilesen tahmin gucu raporlari: hesaplama + Redis onbellegi.

Iki rapor da tum skor gecmisini ve o donemin fiyatlarini okur (yuz binlerce
satir). Kullanici isteginde hesaplanirsa soguk onbellekte sayfa saniyelerce
bekliyordu. Worker her sinyal kosusunda onbellek suresine bakar ve azalmissa
yeniler; API onbellekten okur, yalniz onbellek bossa kendisi hesaplar.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.models import CompositeSignalSnapshot, IndexDaily, PriceDaily
from app.schemas.signal import ComponentPowerOut, SignalHorizonStatOut
from app.signals.accuracy import (
    DEFAULT_HORIZONS,
    ComponentObservation,
    PricePoint,
    SignalObservation,
    compute_component_power,
    compute_signal_accuracy,
)
from app.signals.service import BENCHMARK_INDEX, MODEL_VERSION

logger = logging.getLogger(__name__)

REPORT_KEY = "signals:reports:v1:{model}"
CACHE_TTL_SECONDS = 2 * 60 * 60
# Worker bu sureden az omur kalinca yeniler; kullanici neredeyse hic soguk
# onbellege denk gelmez.
REFRESH_BELOW_SECONDS = 75 * 60


async def build_reports(session: AsyncSession, model_version: str = MODEL_VERSION) -> dict:
    signal_rows = (
        await session.execute(
            select(
                CompositeSignalSnapshot.ticker,
                CompositeSignalSnapshot.as_of_date,
                CompositeSignalSnapshot.composite_score,
                CompositeSignalSnapshot.signal_label,
                CompositeSignalSnapshot.component_scores,
            ).where(CompositeSignalSnapshot.model_version == model_version)
        )
    ).all()
    tickers = {row.ticker for row in signal_rows}
    # Ilk sinyalden onceki fiyatlar hesaba girmez.
    first_signal = min((row.as_of_date for row in signal_rows), default=None)
    price_points: list[PricePoint] = []
    if tickers:
        price_points = [
            PricePoint(row.ticker, row.date, row.close)
            for row in (
                await session.execute(
                    select(PriceDaily.ticker, PriceDaily.date, PriceDaily.close)
                    .where(PriceDaily.ticker.in_(tickers), PriceDaily.date >= first_signal)
                    .order_by(PriceDaily.ticker, PriceDaily.date)
                )
            ).all()
        ]
    benchmark = [
        (row.date, row.value)
        for row in (
            await session.execute(
                select(IndexDaily.date, IndexDaily.value)
                .where(
                    IndexDaily.index_code == BENCHMARK_INDEX,
                    IndexDaily.date >= (first_signal or date.min),
                )
                .order_by(IndexDaily.date)
            )
        ).all()
    ]
    signals = [
        SignalObservation(row.ticker, row.as_of_date, row.composite_score, row.signal_label)
        for row in signal_rows
    ]
    components = [
        ComponentObservation(
            row.ticker,
            row.as_of_date,
            {
                "composite": float(row.composite_score),
                **{key: float(value) for key, value in (row.component_scores or {}).items()},
            },
        )
        for row in signal_rows
    ]
    # Saf Python hesaplari olay dongusunu bloklamasin.
    accuracy = await asyncio.to_thread(
        compute_signal_accuracy,
        signals,
        price_points,
        horizons=DEFAULT_HORIZONS,
        benchmark=benchmark,
    )
    power = await asyncio.to_thread(
        compute_component_power, components, price_points, horizons=DEFAULT_HORIZONS
    )
    return {
        "accuracy": [
            SignalHorizonStatOut.model_validate(item).model_dump(mode="json") for item in accuracy
        ],
        "power": [
            ComponentPowerOut.model_validate(item).model_dump(mode="json") for item in power
        ],
    }


async def _store(reports: dict, model_version: str) -> None:
    try:
        await get_redis().setex(
            REPORT_KEY.format(model=model_version), CACHE_TTL_SECONDS, json.dumps(reports)
        )
    except RedisError as exc:
        logger.debug("Redis cache write error: %s", exc)


async def get_reports(session: AsyncSession, model_version: str = MODEL_VERSION) -> dict:
    """Onbellekteki raporlar; yoksa hesaplayip yazar."""
    try:
        cached = await get_redis().get(REPORT_KEY.format(model=model_version))
        if cached:
            return json.loads(cached)
    except (RedisError, json.JSONDecodeError, TypeError) as exc:
        logger.debug("Redis cache miss or read error: %s", exc)
    reports = await build_reports(session, model_version)
    await _store(reports, model_version)
    return reports


async def refresh_reports_if_stale(
    session: AsyncSession, model_version: str = MODEL_VERSION
) -> bool:
    """Worker icin: onbellek yoksa veya omru azaldiysa yeniden hesaplar."""
    try:
        ttl = await get_redis().ttl(REPORT_KEY.format(model=model_version))
    except RedisError:
        return False
    if ttl > REFRESH_BELOW_SECONDS:
        return False
    await _store(await build_reports(session, model_version), model_version)
    return True

