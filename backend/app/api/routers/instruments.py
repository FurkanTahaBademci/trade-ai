"""Hisse evreni ve fiyat verisi endpoint'leri."""

from datetime import date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.models import Instrument, PriceDaily
from app.schemas.instrument import InstrumentOut, PriceDailyOut

router = APIRouter(prefix="/api/instruments", tags=["instruments"])


@router.get("", response_model=list[InstrumentOut])
async def list_instruments(
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: Annotated[
        bool, Query(description="Sadece aktif (is_active=true) hisseleri dondur")
    ] = True,
) -> list[Instrument]:
    stmt = select(Instrument).order_by(Instrument.ticker)
    if active_only:
        stmt = stmt.where(Instrument.is_active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{ticker}", response_model=InstrumentOut)
async def get_instrument(
    ticker: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> Instrument:
    instrument = await db.get(Instrument, ticker.upper())
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"'{ticker}' bulunamadi")
    return instrument


@router.get("/{ticker}/prices", response_model=list[PriceDailyOut])
async def get_instrument_prices(
    ticker: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    start: Annotated[
        date | None, Query(description="Baslangic tarihi (verilmezse son 90 gun)")
    ] = None,
    end: Annotated[
        date | None, Query(description="Bitis tarihi (verilmezse bugun)")
    ] = None,
) -> list[PriceDaily]:
    ticker = ticker.upper()
    instrument = await db.get(Instrument, ticker)
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"'{ticker}' bulunamadi")

    stmt = select(PriceDaily).where(PriceDaily.ticker == ticker).order_by(PriceDaily.date)
    if start is not None:
        stmt = stmt.where(PriceDaily.date >= start)
    if end is not None:
        stmt = stmt.where(PriceDaily.date <= end)
    if start is None and end is None:
        # Varsayilan: son 90 gun (dashboard grafik icin makul varsayilan)
        today = datetime.now(ZoneInfo(get_settings().tz)).date()
        stmt = stmt.where(PriceDaily.date >= today - timedelta(days=90))

    result = await db.execute(stmt)
    return list(result.scalars().all())
