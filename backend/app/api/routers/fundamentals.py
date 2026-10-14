"""Temel analiz snapshot ve kaynak finansal kalem endpoint'leri."""

from enum import IntEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.valuation import trailing_net_income
from app.models import FinancialFact, FundamentalSnapshot
from app.schemas.fundamental import FinancialFactOut, FundamentalSnapshotOut

router = APIRouter(prefix="/api/fundamentals", tags=["fundamentals"])


class FinancialPeriod(IntEnum):
    THREE_MONTHS = 3
    SIX_MONTHS = 6
    NINE_MONTHS = 9
    TWELVE_MONTHS = 12


@router.get("/{ticker}/facts", response_model=list[FinancialFactOut])
async def list_financial_facts(
    ticker: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    year: Annotated[int | None, Query(ge=2000, le=2200)] = None,
    period: Annotated[FinancialPeriod | None, Query()] = None,
    item_code: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=2_000)] = 500,
) -> list[FinancialFact]:
    stmt = select(FinancialFact).where(FinancialFact.ticker == ticker.upper())
    if year:
        stmt = stmt.where(FinancialFact.year == year)
    if period:
        stmt = stmt.where(FinancialFact.period == period)
    if item_code:
        stmt = stmt.where(FinancialFact.item_code == item_code.upper())
    stmt = stmt.order_by(
        FinancialFact.year.desc(), FinancialFact.period.desc(), FinancialFact.item_code
    )
    return list((await db.scalars(stmt.limit(limit))).all())


@router.get("/{ticker}", response_model=list[FundamentalSnapshotOut])
async def list_fundamental_snapshots(
    ticker: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    year: Annotated[int | None, Query(ge=2000, le=2200)] = None,
    period: Annotated[FinancialPeriod | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[FundamentalSnapshotOut]:
    code = ticker.upper()
    stmt = select(FundamentalSnapshot).where(FundamentalSnapshot.ticker == code)
    if year:
        stmt = stmt.where(FundamentalSnapshot.year == year)
    if period:
        stmt = stmt.where(FundamentalSnapshot.period == period)
    stmt = stmt.order_by(FundamentalSnapshot.year.desc(), FundamentalSnapshot.period.desc())
    rows = list((await db.scalars(stmt.limit(limit))).all())
    if not rows:
        return []
    # TTM icin onceki yilin yillik ve ayni donem kari gerekir; limit/filtre bunlari
    # disarida birakabilecegi icin kucuk bir ek sorguyla okunur.
    years = {row.year for row in rows} | {row.year - 1 for row in rows}
    history_rows = (
        await db.execute(
            select(
                FundamentalSnapshot.financial_group,
                FundamentalSnapshot.year,
                FundamentalSnapshot.period,
                FundamentalSnapshot.net_income,
            ).where(FundamentalSnapshot.ticker == code, FundamentalSnapshot.year.in_(years))
        )
    ).all()
    history: dict[str, dict[tuple[int, int], float | None]] = {}
    for item in history_rows:
        history.setdefault(item.financial_group, {})[(item.year, item.period)] = (
            float(item.net_income) if item.net_income is not None else None
        )
    result = []
    for row in rows:
        out = FundamentalSnapshotOut.model_validate(row)
        ttm, basis = trailing_net_income(
            year=row.year,
            period=row.period,
            net_income=out.net_income,
            history=history.get(row.financial_group, {}),
        )
        result.append(out.model_copy(update={"ttm_net_income": ttm, "ttm_basis": basis}))
    return result
