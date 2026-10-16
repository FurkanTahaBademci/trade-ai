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
from decimal import Decimal

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.models import CompositeSignalSnapshot, IndexDaily, PriceDaily
from app.schemas.signal import ComponentPowerOut, SignalHorizonStatOut, WeightScenarioOut
from app.signals.accuracy import (
    DEFAULT_HORIZONS,
    POWER_COMPONENTS,
    ComponentObservation,
    PricePoint,
    SignalObservation,
    compute_component_power,
    compute_signal_accuracy,
)
from app.signals.service import (
    BENCHMARK_INDEX,
    COMPONENT_WEIGHTS,
    MODEL_VERSION,
    recombine_score,
)

logger = logging.getLogger(__name__)

# v2: agirlik senaryolari eklendi (eski onbellekte yoktu).
REPORT_KEY = "signals:reports:v2:{model}"
CACHE_TTL_SECONDS = 2 * 60 * 60
# Worker bu sureden az omur kalinca yeniler; kullanici neredeyse hic soguk
# onbellege denk gelmez.
REFRESH_BELOW_SECONDS = 75 * 60

# Model v4 adaylari. 6 aylik IC'de analist bileseni negatif cikti; senaryolar,
# canli model degismeden once farkli agirliklarin ayni gecmiste ne verdigini
# surekli (her rapor yenilemesinde) gosterir. Agirliklar toplami 1.
WEIGHT_SCENARIOS: tuple[tuple[str, str, dict[str, Decimal]], ...] = (
    ("current", "Canlı model (v3)", dict(COMPONENT_WEIGHTS)),
    (
        "analyst_low",
        "Analist %10",
        {
            "llm": Decimal("0.40"),
            "fundamental": Decimal("0.32"),
            "analyst": Decimal("0.10"),
            "momentum": Decimal("0.18"),
        },
    ),
    (
        "analyst_off",
        "Analist yok",
        {
            "llm": Decimal("0.45"),
            "fundamental": Decimal("0.35"),
            "analyst": Decimal(0),
            "momentum": Decimal("0.20"),
        },
    ),
    (
        "price_heavy",
        "Temel + momentum ağırlıklı",
        {
            "llm": Decimal("0.30"),
            "fundamental": Decimal("0.35"),
            "analyst": Decimal("0.10"),
            "momentum": Decimal("0.25"),
        },
    ),
    ("equal", "Eşit ağırlık", {name: Decimal("0.25") for name in COMPONENT_WEIGHTS}),
)
_SCENARIO_PREFIX = "scenario:"


async def build_reports(session: AsyncSession, model_version: str = MODEL_VERSION) -> dict:
    signal_rows = (
        await session.execute(
            select(
                CompositeSignalSnapshot.ticker,
                CompositeSignalSnapshot.as_of_date,
                CompositeSignalSnapshot.composite_score,
                CompositeSignalSnapshot.signal_label,
                CompositeSignalSnapshot.component_scores,
                CompositeSignalSnapshot.confidence,
                CompositeSignalSnapshot.evidence["confidences"].label("component_confidences"),
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
                **_scenario_scores(row),
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
        compute_component_power,
        components,
        price_points,
        horizons=DEFAULT_HORIZONS,
        components=POWER_COMPONENTS
        + tuple(_SCENARIO_PREFIX + key for key, _, _ in WEIGHT_SCENARIOS),
    )
    return {
        "accuracy": [
            SignalHorizonStatOut.model_validate(item).model_dump(mode="json") for item in accuracy
        ],
        "power": [
            ComponentPowerOut.model_validate(item).model_dump(mode="json")
            for item in power
            if item.component in POWER_COMPONENTS
        ],
        "scenarios": scenario_reports(power),
    }


def _scenario_scores(row) -> dict[str, float]:
    """Satirin her agirlik senaryosundaki yeniden birlestirilmis skoru."""
    scores: dict[str, float] = {}
    for key, _, weights in WEIGHT_SCENARIOS:
        value = recombine_score(
            row.component_scores or {},
            weights,
            confidence=Decimal(str(row.confidence)),
            component_confidences=row.component_confidences,
        )
        if value is not None:
            scores[_SCENARIO_PREFIX + key] = float(value)
    return scores


def scenario_reports(power) -> list[dict]:
    labels = {key: (label, weights) for key, label, weights in WEIGHT_SCENARIOS}
    rows = []
    for item in power:
        if not item.component.startswith(_SCENARIO_PREFIX):
            continue
        key = item.component.removeprefix(_SCENARIO_PREFIX)
        label, weights = labels[key]
        rows.append(
            WeightScenarioOut(
                key=key,
                label=label,
                weights={name: float(value) for name, value in weights.items()},
                horizon=item.horizon,
                days=item.days,
                observations=item.observations,
                mean_ic=item.mean_ic,
                positive_ic_pct=item.positive_ic_pct,
                spread_pct=item.spread_pct,
            ).model_dump(mode="json")
        )
    return rows


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
