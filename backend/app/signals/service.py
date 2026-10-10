"""Aciklanabilir, deterministik bilesik skor motoru.

V3 agirliklari:
  LLM haber/KAP etkisi  %35
  Temel analiz          %28
  Analist konsensusu    %22
  Fiyat momentumu       %15

Eksik bir kaynak sifir puan sayilmaz. Mevcut agirliklar yeniden normalize
edilir; `confidence` kapsama ve kaynak kalitesini ayrica ifade eder.

V1'den farklar (v2 yayinlanmadan v3'e birlestirildi):
- TEFAS akimi piyasa geneli tek bir sayidir, hisse ayristirmaz; her hisseye
  ayni puani verip bilesen sayisini sisirdigi icin bilesik skordan cikarildi.
- Analist guveni ortalama tavsiye yasiyla azalir (bayat hedef fiyat).
- Ham skor guvene gore 50'ye dogru cekilir; az kanitli hisse listenin
  tepesine cikamaz. Ham skor `evidence.raw_score` icinde saklanir.
- Gecmis tarih icin calistirildiginda o tarihte bilinmeyen veri kullanilmaz.
- Momentum: hissenin XU100'e gore 20 ve 60 islem gunluk goreli getirisi.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from types import SimpleNamespace
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.analysts import ANALYST_MAX_AGE_DAYS, calculate_consensus
from app.models import (
    AnalystRecommendation,
    CompositeSignalSnapshot,
    FundamentalSnapshot,
    IndexDaily,
    Instrument,
    LlmEvaluation,
    PriceDaily,
)

MODEL_VERSION = "v3"
COMPONENT_WEIGHTS = {
    "llm": Decimal("0.35"),
    "fundamental": Decimal("0.28"),
    "analyst": Decimal("0.22"),
    "momentum": Decimal("0.15"),
}
BENCHMARK_INDEX = "XU100"
MOMENTUM_SHORT_DAYS = 20
MOMENTUM_LONG_DAYS = 60
# Goreli getiri puana cevrilirken +/- %25 0/100 bandina gelir.
MOMENTUM_SCALE = Decimal(2)
MOMENTUM_MAX_STALE_DAYS = 7
LLM_LOOKBACK_DAYS = 14
MIN_COMPONENTS = 2
# Bu guvenin altinda skor 50'ye dogru orantili cekilir (0 guven -> 50).
FULL_CONFIDENCE = Decimal("0.60")
# Ortalama tavsiye yasi bu kadar gun oldugunda analist guveni yariya iner.
ANALYST_CONFIDENCE_HALF_LIFE_DAYS = 120


@dataclass(frozen=True)
class ComponentResult:
    score: Decimal
    confidence: Decimal
    evidence: dict[str, Any]


def _decimal(value: Any, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


def _clamp(value: Decimal, minimum: Decimal = Decimal(0), maximum: Decimal = Decimal(100)) -> Decimal:
    return max(minimum, min(maximum, value))


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def signal_label(score: Decimal | float) -> str:
    value = _decimal(score)
    if value >= 75:
        return "VERY_POSITIVE"
    if value >= 60:
        return "POSITIVE"
    if value >= 40:
        return "NEUTRAL"
    if value >= 25:
        return "NEGATIVE"
    return "VERY_NEGATIVE"


def score_llm_evaluations(
    rows: list[Any], ticker: str, *, now: datetime
) -> ComponentResult | None:
    """Ayni kaynak icin Tier 2'yi tercih edip duygu/etkiyi tazelikle birlestirir."""
    matching = [row for row in rows if ticker in (row.ticker_codes or [])]
    if not matching:
        return None

    deduplicated: dict[tuple[str, int], Any] = {}
    for row in matching:
        key = (row.source_type, row.source_id)
        current = deduplicated.get(key)
        row_time = row.completed_at or row.created_at
        current_time = (current.completed_at or current.created_at) if current else None
        if current is None or (row.tier, _aware(row_time)) > (current.tier, _aware(current_time)):
            deduplicated[key] = row

    weighted_score = Decimal(0)
    total_weight = Decimal(0)
    confidence_sum = Decimal(0)
    evidence_ids: list[int] = []
    for row in deduplicated.values():
        timestamp = _aware(row.completed_at or row.created_at)
        age_days = max(0.0, (now - timestamp).total_seconds() / 86_400)
        recency = Decimal(str(0.5 ** (age_days / 3)))
        confidence = _clamp(_decimal(row.confidence, "0.5"), Decimal(0), Decimal(1))
        weight = max(Decimal("0.02"), confidence * recency)
        direction = _clamp(_decimal(row.sentiment_score), Decimal(-1), Decimal(1))
        impact = _clamp(_decimal(row.impact_score)) / 100
        relevance = _clamp(_decimal(row.relevance_score)) / 100
        score = _clamp(Decimal(50) + Decimal(50) * direction * impact * relevance)
        weighted_score += score * weight
        confidence_sum += confidence * weight
        total_weight += weight
        evidence_ids.append(row.id)

    return ComponentResult(
        score=weighted_score / total_weight,
        confidence=confidence_sum / total_weight,
        evidence={"evaluation_ids": sorted(evidence_ids), "document_count": len(evidence_ids)},
    )


def score_fundamental(row: Any) -> ComponentResult | None:
    if row is None or row.fundamental_score is None:
        return None
    completeness = min(1, max(0, int(row.data_completeness)) / 11)
    return ComponentResult(
        score=_clamp(_decimal(row.fundamental_score)),
        confidence=Decimal(str(completeness)),
        evidence={
            "snapshot_id": row.id,
            "period": f"{row.year}/{row.period}",
            "data_completeness": row.data_completeness,
        },
    )


def score_analyst(row: Any) -> ComponentResult | None:
    if row is None or row.recommendation_score is None:
        return None
    institution_count = max(0, int(row.institution_count))
    confidence = min(1, institution_count / 8)
    average_age = getattr(row, "average_age_days", None)
    if average_age is not None:
        confidence *= 0.5 ** (float(average_age) / ANALYST_CONFIDENCE_HALF_LIFE_DAYS)
    vote_score = _clamp(_decimal(row.recommendation_score))
    if row.implied_upside_pct is not None:
        # +/- %100 hedef potansiyeli 0/100 bandina gelir. Oy dagilimi daha
        # guvenilir oldugu icin bilesenin %75'ini korur.
        target_score = _clamp(Decimal(50) + _decimal(row.implied_upside_pct) / 2)
        score = vote_score * Decimal("0.75") + target_score * Decimal("0.25")
    else:
        score = vote_score
    return ComponentResult(
        score=score,
        confidence=Decimal(str(confidence)),
        evidence={
            "consensus_id": row.id,
            "as_of_date": row.as_of_date.isoformat(),
            "institution_count": institution_count,
            "average_age_days": float(average_age) if average_age is not None else None,
            "implied_upside_pct": (
                float(row.implied_upside_pct) if row.implied_upside_pct is not None else None
            ),
        },
    )


def _value_at_or_before(series: list[tuple[date, Decimal]], target: date) -> Decimal | None:
    index = bisect_right(series, (target, Decimal("Infinity"))) - 1
    return series[index][1] if index >= 0 else None


def score_momentum(
    closes: list[tuple[date, Decimal]],
    benchmark: list[tuple[date, Decimal]],
    *,
    as_of_date: date,
) -> ComponentResult | None:
    """XU100'e gore goreli getiri; `closes` ve `benchmark` tarihe gore sirali olmali."""
    usable = [(day, close) for day, close in closes if day <= as_of_date and close > 0]
    if len(usable) <= MOMENTUM_SHORT_DAYS:
        return None
    last_day, last_close = usable[-1]
    stale_days = (as_of_date - last_day).days
    if stale_days > MOMENTUM_MAX_STALE_DAYS:
        return None
    bench_last = _value_at_or_before(benchmark, last_day)
    if not bench_last:
        return None

    relatives: dict[int, Decimal] = {}
    for window in (MOMENTUM_SHORT_DAYS, MOMENTUM_LONG_DAYS):
        if len(usable) <= window:
            continue
        base_day, base_close = usable[-1 - window]
        bench_base = _value_at_or_before(benchmark, base_day)
        if not bench_base:
            continue
        stock_return = (last_close / base_close - 1) * 100
        bench_return = (bench_last / bench_base - 1) * 100
        relatives[window] = stock_return - bench_return
    if MOMENTUM_SHORT_DAYS not in relatives:
        return None

    if MOMENTUM_LONG_DAYS in relatives:
        blended = (
            relatives[MOMENTUM_SHORT_DAYS] * Decimal("0.6")
            + relatives[MOMENTUM_LONG_DAYS] * Decimal("0.4")
        )
        coverage = Decimal(1)
    else:
        blended = relatives[MOMENTUM_SHORT_DAYS]
        coverage = Decimal("0.6")
    freshness = Decimal(1) if stale_days <= 3 else Decimal("0.7")
    return ComponentResult(
        score=_clamp(Decimal(50) + blended * MOMENTUM_SCALE),
        confidence=coverage * freshness,
        evidence={
            "price_date": last_day.isoformat(),
            "relative_20d_pct": float(relatives[MOMENTUM_SHORT_DAYS].quantize(Decimal("0.01"))),
            "relative_60d_pct": (
                float(relatives[MOMENTUM_LONG_DAYS].quantize(Decimal("0.01")))
                if MOMENTUM_LONG_DAYS in relatives
                else None
            ),
        },
    )


def build_composite_signal(
    ticker: str,
    components: dict[str, ComponentResult],
    *,
    as_of_date: date,
) -> dict[str, Any] | None:
    available = {name: value for name, value in components.items() if name in COMPONENT_WEIGHTS}
    if len(available) < MIN_COMPONENTS:
        return None
    available_weight = sum((COMPONENT_WEIGHTS[name] for name in available), Decimal(0))
    effective = {name: COMPONENT_WEIGHTS[name] / available_weight for name in available}
    composite = sum((available[name].score * effective[name] for name in available), Decimal(0))
    quality = sum((available[name].confidence * effective[name] for name in available), Decimal(0))
    coverage_factor = available_weight / sum(COMPONENT_WEIGHTS.values())
    confidence = _clamp(quality * coverage_factor, Decimal(0), Decimal(1))
    shrink = min(Decimal(1), confidence / FULL_CONFIDENCE)
    adjusted = Decimal(50) + (composite - Decimal(50)) * shrink
    rounded_score = adjusted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "ticker": ticker,
        "as_of_date": as_of_date,
        "model_version": MODEL_VERSION,
        "composite_score": rounded_score,
        "signal_label": signal_label(rounded_score),
        "confidence": confidence.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP),
        "coverage_count": len(available),
        "component_scores": {
            name: float(value.score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            for name, value in available.items()
        },
        "component_weights": {
            name: float(weight.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
            for name, weight in effective.items()
        },
        "evidence": {
            **{name: value.evidence for name, value in available.items()},
            "raw_score": float(composite.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        },
    }


def _latest_by_ticker(rows: list[Any], key) -> dict[str, Any]:
    latest: dict[str, Any] = {}
    for row in rows:
        current = latest.get(row.ticker)
        if current is None or key(row) > key(current):
            latest[row.ticker] = row
    return latest


async def run_signal_engine(
    session: AsyncSession,
    *,
    tickers: list[str] | None = None,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    as_of = as_of_date or datetime.now().astimezone().date()
    # Gun icinde ayni girdiler ayni sonucu uretsin; recency referansi sabittir.
    now = datetime.combine(as_of, time.max, tzinfo=UTC)
    active = set(
        (
            await session.scalars(select(Instrument.ticker).where(Instrument.is_active.is_(True)))
        ).all()
    )
    requested = {ticker.strip().upper() for ticker in tickers or [] if ticker.strip()}
    if requested:
        active &= requested

    llm_rows = list(
        (
            await session.scalars(
                select(LlmEvaluation).where(
                    LlmEvaluation.status == "succeeded",
                    LlmEvaluation.created_at
                    >= datetime.combine(as_of, time.min, tzinfo=UTC)
                    - timedelta(days=LLM_LOOKBACK_DAYS),
                    LlmEvaluation.created_at <= now,
                )
            )
        ).all()
    )
    fundamental_rows = list(
        (
            await session.scalars(
                select(FundamentalSnapshot).where(
                    FundamentalSnapshot.fundamental_score.is_not(None),
                    FundamentalSnapshot.computed_at <= now,
                )
            )
        ).all()
    )
    # Konsensus tablosu UI icin gunluk bir ozettir; skor motoru o tarihte
    # gecerli tavsiyelerden ayni formulle anlik hesaplar (geriye donuk
    # hesaplarda da yas agirligi ve bakis-onyargisi korumasi gecerli olur).
    recommendation_rows = list(
        (
            await session.scalars(
                select(AnalystRecommendation).where(
                    AnalystRecommendation.recommendation_date <= as_of,
                    AnalystRecommendation.recommendation_date
                    >= as_of - timedelta(days=ANALYST_MAX_AGE_DAYS),
                )
            )
        ).all()
    )
    price_rows = (
        await session.execute(
            select(PriceDaily.ticker, PriceDaily.close)
            .where(PriceDaily.date <= as_of)
            .distinct(PriceDaily.ticker)
            .order_by(PriceDaily.ticker, PriceDaily.date.desc())
        )
    ).all()
    # Momentum icin ~60 islem gunu + tatiller: 120 takvim gunu yeterli.
    momentum_start = as_of - timedelta(days=120)
    closes_by_ticker: dict[str, list[tuple[date, Decimal]]] = {}
    for ticker, day, close in (
        await session.execute(
            select(PriceDaily.ticker, PriceDaily.date, PriceDaily.close)
            .where(
                PriceDaily.date >= momentum_start,
                PriceDaily.date <= as_of,
                PriceDaily.ticker.in_(active),
            )
            .order_by(PriceDaily.ticker, PriceDaily.date)
        )
    ).all():
        if close is not None:
            closes_by_ticker.setdefault(ticker, []).append((day, Decimal(str(close))))
    benchmark = [
        (day, Decimal(str(value)))
        for day, value in (
            await session.execute(
                select(IndexDaily.date, IndexDaily.value)
                .where(
                    IndexDaily.index_code == BENCHMARK_INDEX,
                    IndexDaily.date >= momentum_start,
                    IndexDaily.date <= as_of,
                )
                .order_by(IndexDaily.date)
            )
        ).all()
        if value
    ]
    analysts = {
        row["ticker"]: SimpleNamespace(id=None, **row)
        for row in calculate_consensus(
            recommendation_rows, market_prices=dict(price_rows), as_of_date=as_of
        )
    }
    fundamentals = _latest_by_ticker(
        fundamental_rows, lambda row: (row.year, row.period, row.computed_at)
    )
    candidates = set(fundamentals) | set(analysts)
    candidates |= {ticker for row in llm_rows for ticker in (row.ticker_codes or [])}
    candidates &= active

    snapshots: list[dict[str, Any]] = []
    skipped_low_coverage = 0
    for ticker in sorted(candidates):
        components: dict[str, ComponentResult] = {}
        llm = score_llm_evaluations(llm_rows, ticker, now=now)
        fundamental = score_fundamental(fundamentals.get(ticker))
        analyst = score_analyst(analysts.get(ticker))
        if llm:
            components["llm"] = llm
        if fundamental:
            components["fundamental"] = fundamental
        if analyst:
            components["analyst"] = analyst
        momentum = score_momentum(
            closes_by_ticker.get(ticker, []), benchmark, as_of_date=as_of
        )
        if momentum:
            components["momentum"] = momentum
        snapshot = build_composite_signal(ticker, components, as_of_date=as_of)
        if snapshot:
            snapshots.append(snapshot)
        else:
            skipped_low_coverage += 1

    existing = set(
        (
            await session.scalars(
                select(CompositeSignalSnapshot.ticker).where(
                    CompositeSignalSnapshot.as_of_date == as_of,
                    CompositeSignalSnapshot.model_version == MODEL_VERSION,
                    CompositeSignalSnapshot.ticker.in_([row["ticker"] for row in snapshots]),
                )
            )
        ).all()
    ) if snapshots else set()

    if snapshots:
        stmt = pg_insert(CompositeSignalSnapshot).values(snapshots)
        await session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_composite_signal_identity",
                set_={
                    "composite_score": stmt.excluded.composite_score,
                    "signal_label": stmt.excluded.signal_label,
                    "confidence": stmt.excluded.confidence,
                    "coverage_count": stmt.excluded.coverage_count,
                    "component_scores": stmt.excluded.component_scores,
                    "component_weights": stmt.excluded.component_weights,
                    "evidence": stmt.excluded.evidence,
                    "computed_at": func.now(),
                    "updated_at": func.now(),
                },
            )
        )
        await session.commit()
    return {
        "model_version": MODEL_VERSION,
        "as_of_date": as_of.isoformat(),
        "candidates": len(candidates),
        "snapshots": len(snapshots),
        "new": len({row["ticker"] for row in snapshots} - existing),
        "updated": len(existing),
        "skipped_low_coverage": skipped_low_coverage,
    }
