"""Bilesik skor siralamasi ve ticker gecmisi endpoint'leri."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models import CompositeSignalSnapshot
from app.schemas.signal import CompositeSignalOut

router = APIRouter(prefix="/api/signals", tags=["signals"])


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
    target_date = as_of or await db.scalar(select(func.max(CompositeSignalSnapshot.as_of_date)))
    if target_date is None:
        return []
    stmt = select(CompositeSignalSnapshot).where(
        CompositeSignalSnapshot.as_of_date == target_date
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


@router.get("/{ticker}", response_model=list[CompositeSignalOut])
async def signal_history(
    ticker: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=365)] = 90,
) -> list[CompositeSignalSnapshot]:
    stmt = (
        select(CompositeSignalSnapshot)
        .where(CompositeSignalSnapshot.ticker == ticker.upper())
        .order_by(CompositeSignalSnapshot.as_of_date.desc())
        .limit(limit)
    )
    return list((await db.scalars(stmt)).all())
