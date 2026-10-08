"""BIST endeks (BIST100/XU100) gunluk deger endpoint'i."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models import IndexDaily
from app.schemas.index_price import IndexDailyOut

router = APIRouter(prefix="/api/index", tags=["index"])


@router.get("/{code}/prices", response_model=list[IndexDailyOut])
async def get_index_prices(
    code: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    start: Annotated[date | None, Query(description="Baslangic tarihi")] = None,
    end: Annotated[date | None, Query(description="Bitis tarihi")] = None,
) -> list[IndexDaily]:
    stmt = select(IndexDaily).where(IndexDaily.index_code == code.upper()).order_by(IndexDaily.date)
    if start is not None:
        stmt = stmt.where(IndexDaily.date >= start)
    if end is not None:
        stmt = stmt.where(IndexDaily.date <= end)
    result = await db.execute(stmt)
    return list(result.scalars().all())
