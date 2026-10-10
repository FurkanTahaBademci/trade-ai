"""TCMB faiz kararlari ve etki senaryolari endpoint'leri."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.evds import EVDS_SERIES
from app.core.db import get_db
from app.models import MacroSeriesPoint, MonetaryPolicyDecision
from app.schemas.macro import MacroSeriesOut, MonetaryPolicyDecisionOut

router = APIRouter(prefix="/api/macro", tags=["macro"])


@router.get("/policy-decisions", response_model=list[MonetaryPolicyDecisionOut])
async def list_policy_decisions(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[Literal["PUBLISHED", "SCHEDULED"] | None, Query()] = None,
    start: Annotated[date | None, Query()] = None,
    end: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[MonetaryPolicyDecision]:
    stmt = select(MonetaryPolicyDecision)
    if status:
        stmt = stmt.where(MonetaryPolicyDecision.status == status)
    if start:
        stmt = stmt.where(MonetaryPolicyDecision.decision_date >= start)
    if end:
        stmt = stmt.where(MonetaryPolicyDecision.decision_date <= end)
    stmt = stmt.order_by(MonetaryPolicyDecision.decision_date.desc()).limit(limit)
    return list((await db.scalars(stmt)).all())


def summarize_series(code: str, points: list[tuple[date, float]]) -> MacroSeriesOut:
    """Son deger, onceki gozleme gore degisim ve (aylik seride) yillik degisim."""
    ordered = sorted(points)
    latest = ordered[-1] if ordered else None
    previous = ordered[-2] if len(ordered) >= 2 else None
    year_ago = None
    # Yillik degisim yalniz aylik seride (TUFE) anlamli; EVDS aylik gozlemleri ayin 1'i.
    monthly = bool(ordered) and all(day.day == 1 for day, _ in ordered)
    if latest and monthly:
        target = latest[0].replace(year=latest[0].year - 1)
        year_ago = next((value for day, value in ordered if day == target), None)
    return MacroSeriesOut(
        code=code,
        label=EVDS_SERIES.get(code, code),
        latest_date=latest[0] if latest else None,
        latest_value=latest[1] if latest else None,
        change_pct=(
            (latest[1] / previous[1] - 1) * 100 if latest and previous and previous[1] else None
        ),
        yoy_pct=(latest[1] / year_ago - 1) * 100 if latest and year_ago else None,
        history=[{"date": day, "value": value} for day, value in ordered[-60:]],
    )


@router.get("/series", response_model=list[MacroSeriesOut])
async def list_macro_series(db: Annotated[AsyncSession, Depends(get_db)]) -> list[MacroSeriesOut]:
    rows = (
        await db.execute(
            select(MacroSeriesPoint.series_code, MacroSeriesPoint.date, MacroSeriesPoint.value)
            .where(MacroSeriesPoint.date >= date.today().replace(day=1, year=date.today().year - 2))
            .order_by(MacroSeriesPoint.series_code, MacroSeriesPoint.date)
        )
    ).all()
    grouped: dict[str, list[tuple[date, float]]] = {code: [] for code in EVDS_SERIES}
    for code, day, value in rows:
        grouped.setdefault(code, []).append((day, float(value)))
    return [summarize_series(code, points) for code, points in grouped.items() if points]
