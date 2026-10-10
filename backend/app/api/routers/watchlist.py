"""Yonetici izleme listesi: web arayuzuyle senkron, bildirimlerin girdisi."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.schedules import require_admin_token
from app.core.db import get_db
from app.models import WatchlistItem

router = APIRouter(
    prefix="/api/watchlist",
    tags=["watchlist"],
    dependencies=[Depends(require_admin_token)],
)
MAX_WATCHLIST_SIZE = 200


class WatchlistIn(BaseModel):
    tickers: list[str] = Field(default_factory=list, max_length=MAX_WATCHLIST_SIZE)


class WatchlistOut(BaseModel):
    tickers: list[str]


def normalize_tickers(raw: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in raw:
        ticker = item.strip().upper()
        if ticker and len(ticker) <= 16 and ticker.isalnum():
            seen.setdefault(ticker, None)
    return list(seen)


async def _current(db: AsyncSession) -> list[str]:
    rows = await db.scalars(select(WatchlistItem.ticker).order_by(WatchlistItem.added_at))
    return list(rows.all())


@router.get("", response_model=WatchlistOut)
async def get_watchlist(db: Annotated[AsyncSession, Depends(get_db)]) -> WatchlistOut:
    return WatchlistOut(tickers=await _current(db))


@router.put("", response_model=WatchlistOut)
async def replace_watchlist(
    body: WatchlistIn, db: Annotated[AsyncSession, Depends(get_db)]
) -> WatchlistOut:
    """Listeyi verilenle degistirir; ayni govdeyle tekrar cagrilmasi etkisizdir."""
    tickers = normalize_tickers(body.tickers)
    await db.execute(delete(WatchlistItem).where(WatchlistItem.ticker.not_in(tickers)))
    if tickers:
        await db.execute(
            pg_insert(WatchlistItem)
            .values([{"ticker": ticker} for ticker in tickers])
            .on_conflict_do_nothing(index_elements=[WatchlistItem.ticker])
        )
    await db.commit()
    return WatchlistOut(tickers=await _current(db))
