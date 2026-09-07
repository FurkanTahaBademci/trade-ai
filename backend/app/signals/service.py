"""Aciklanabilir, deterministik bilesik skor motoru.

V1 agirliklari:
  LLM haber/KAP etkisi  %35
  Temel analiz          %30
  Analist konsensusu    %25
  TEFAS piyasa akimi    %10

Eksik bir kaynak sifir puan sayilmaz. Mevcut agirliklar yeniden normalize
edilir; `confidence` kapsama ve kaynak kalitesini ayrica ifade eder.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalystConsensus,
    CompositeSignalSnapshot,
    FundamentalSnapshot,
    FundFlowAggregate,
    Instrument,
    LlmEvaluation,
)

MODEL_VERSION = "v1"
COMPONENT_WEIGHTS = {
    "llm": Decimal("0.35"),
    "fundamental": Decimal("0.30"),
    "analyst": Decimal("0.25"),
    "fund_flow": Decimal("0.10"),
}
LLM_LOOKBACK_DAYS = 14
MIN_COMPONENTS = 2


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
            "implied_upside_pct": (
                float(row.implied_upside_pct) if row.implied_upside_pct is not None else None
            ),
        },
    )


def score_fund_flow(row: Any, *, as_of_date: date) -> ComponentResult | None:
    if row is None or row.total_aum in (None, 0) or row.estimated_stock_flow is None:
        return None
    age_days = (as_of_date - row.date).days
    if age_days < 0 or age_days > 7:
        return None
    # +/- %0,5 tahmini hisse akimi, buyukluk alt skorunun 0/100 siniridir.
    flow_ratio = _decimal(row.estimated_stock_flow) / _decimal(row.total_aum)
    magnitude_score = _clamp(Decimal(50) + flow_ratio * Decimal(10_000))
    breadth_score = _clamp(_decimal(row.positive_flow_pct, "50"))
    score = magnitude_score * Decimal("0.70") + breadth_score * Decimal("0.30")
    observed = max(0, int(row.flow_observation_count))
    funds = max(1, int(row.fund_count))
    observation_quality = min(1, observed / funds)
    freshness = max(0.5, 1 - age_days / 14)
    return ComponentResult(
        score=score,
        confidence=Decimal(str(observation_quality * freshness)),
        evidence={
            "aggregate_id": row.id,
            "date": row.date.isoformat(),
            "fund_count": row.fund_count,
            "estimated_stock_flow": float(row.estimated_stock_flow),
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
    rounded_score = composite.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
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
        "evidence": {name: value.evidence for name, value in available.items()},
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
                )
            )
        ).all()
    )
    fundamental_rows = list(
        (
            await session.scalars(
                select(FundamentalSnapshot).where(
                    FundamentalSnapshot.fundamental_score.is_not(None)
                )
            )
        ).all()
    )
    analyst_rows = list(
        (
            await session.scalars(
                select(AnalystConsensus).where(AnalystConsensus.as_of_date <= as_of)
            )
        ).all()
    )
    flow = await session.scalar(
        select(FundFlowAggregate)
        .where(FundFlowAggregate.fund_kind == "YAT", FundFlowAggregate.date <= as_of)
        .order_by(FundFlowAggregate.date.desc())
        .limit(1)
    )

    fundamentals = _latest_by_ticker(
        fundamental_rows, lambda row: (row.year, row.period, row.computed_at)
    )
    analysts = _latest_by_ticker(analyst_rows, lambda row: (row.as_of_date, row.computed_at))
    candidates = set(fundamentals) | set(analysts)
    candidates |= {ticker for row in llm_rows for ticker in (row.ticker_codes or [])}
    candidates &= active

    flow_component = score_fund_flow(flow, as_of_date=as_of)
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
        if flow_component:
            components["fund_flow"] = flow_component
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
