"""Tarihsel strateji degerlendirme endpoint'leri."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.schedules import require_admin_token
from app.backtest.service import create_backtest_run, get_backtest_run
from app.core.db import get_db
from app.models import BacktestRun
from app.schemas.backtest import BacktestCreate, BacktestRunDetailOut, BacktestRunSummaryOut

router = APIRouter(prefix="/api/backtests", tags=["backtests"])


@router.post("", response_model=BacktestRunDetailOut, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: BacktestCreate,
    _admin: Annotated[str, Depends(require_admin_token)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BacktestRun:
    return await create_backtest_run(db, payload)


@router.get("", response_model=list[BacktestRunSummaryOut])
async def list_runs(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[BacktestRun]:
    return list(
        (
            await db.scalars(
                select(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(limit)
            )
        ).all()
    )


@router.get("/{run_id}", response_model=BacktestRunDetailOut)
async def get_run(run_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> BacktestRun:
    run = await get_backtest_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Backtest kosusu bulunamadi")
    return run
