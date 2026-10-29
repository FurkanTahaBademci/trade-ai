"""Yonetici (sistem) backtest kosulari.

Bu uclar yalniz sahibi bos kosulari gosterir; kullanicilarin kosulari
`/api/me/backtests` altindadir. Kosu kuyruga yazilir ve worker'da hesaplanir.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.schedules import require_admin_token
from app.backtest.service import get_backtest_run, queue_backtest_run
from app.core.db import get_db
from app.models import BacktestRun, BacktestRunTrade
from app.schemas.backtest import (
    BacktestCreate,
    BacktestRunDetailOut,
    BacktestRunSummaryOut,
    BacktestTradeOut,
)

router = APIRouter(prefix="/api/backtests", tags=["backtests"])


@router.post("", response_model=BacktestRunDetailOut, status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    payload: BacktestCreate,
    _admin: Annotated[str, Depends(require_admin_token)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BacktestRun:
    return await queue_backtest_run(db, payload, owner_id=None)


@router.get("", response_model=list[BacktestRunSummaryOut])
async def list_runs(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    before_id: Annotated[int | None, Query(ge=1)] = None,
) -> list[BacktestRun]:
    stmt = select(BacktestRun).where(BacktestRun.owner_id.is_(None))
    if before_id is not None:
        stmt = stmt.where(BacktestRun.id < before_id)
    return list((await db.scalars(stmt.order_by(BacktestRun.id.desc()).limit(limit))).all())


@router.get("/{run_id}", response_model=BacktestRunDetailOut)
async def get_run(
    run_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    include_trades: bool = True,
) -> BacktestRun:
    run = await get_backtest_run(db, run_id, include_trades=include_trades)
    if run is None or run.owner_id is not None:
        raise HTTPException(status_code=404, detail="Backtest kosusu bulunamadi")
    return run


@router.get("/{run_id}/trades", response_model=list[BacktestTradeOut])
async def list_run_trades(
    run_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    ticker: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
    side: Literal["BUY", "SELL"] | None = None,
    before_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[BacktestRunTrade]:
    if (
        await db.scalar(
            select(BacktestRun.id).where(BacktestRun.id == run_id, BacktestRun.owner_id.is_(None))
        )
        is None
    ):
        raise HTTPException(status_code=404, detail="Backtest kosusu bulunamadi")
    return await run_trades(db, run_id, ticker=ticker, side=side, before_id=before_id, limit=limit)


async def run_trades(
    db: AsyncSession,
    run_id: int,
    *,
    ticker: str | None,
    side: str | None,
    before_id: int | None,
    limit: int,
) -> list[BacktestRunTrade]:
    stmt = select(BacktestRunTrade).where(BacktestRunTrade.run_id == run_id)
    if ticker:
        stmt = stmt.where(BacktestRunTrade.ticker == ticker.strip().upper())
    if side:
        stmt = stmt.where(BacktestRunTrade.side == side)
    if before_id is not None:
        stmt = stmt.where(BacktestRunTrade.id < before_id)
    return list((await db.scalars(stmt.order_by(BacktestRunTrade.id.desc()).limit(limit))).all())
