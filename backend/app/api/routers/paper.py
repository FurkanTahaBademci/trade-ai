"""Paper portfoy, pozisyon, islem ve performans endpoint'leri."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models import PaperPortfolio, PaperPortfolioSnapshot, PaperPosition, PaperTrade
from app.schemas.paper import (
    PaperPortfolioOut,
    PaperPortfolioSnapshotOut,
    PaperPositionOut,
    PaperTradeOut,
)

router = APIRouter(prefix="/api/paper", tags=["paper-portfolio"])


@router.get("/portfolios", response_model=list[PaperPortfolioOut])
async def list_portfolios(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PaperPortfolio]:
    return list((await db.scalars(select(PaperPortfolio).order_by(PaperPortfolio.id))).all())


@router.get("/portfolios/{portfolio_id}", response_model=PaperPortfolioOut)
async def get_portfolio(
    portfolio_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> PaperPortfolio:
    portfolio = await db.get(PaperPortfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Paper portfoy bulunamadi")
    return portfolio


@router.get("/portfolios/{portfolio_id}/positions", response_model=list[PaperPositionOut])
async def list_positions(
    portfolio_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    ticker: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
) -> list[PaperPosition]:
    stmt = select(PaperPosition).where(PaperPosition.portfolio_id == portfolio_id)
    if ticker:
        stmt = stmt.where(PaperPosition.ticker == ticker.upper())
    stmt = stmt.order_by(PaperPosition.market_value.desc(), PaperPosition.ticker)
    return list((await db.scalars(stmt)).all())


@router.get("/portfolios/{portfolio_id}/trades", response_model=list[PaperTradeOut])
async def list_trades(
    portfolio_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    ticker: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
    limit: Annotated[int, Query(ge=1, le=1_000)] = 100,
) -> list[PaperTrade]:
    stmt = select(PaperTrade).where(PaperTrade.portfolio_id == portfolio_id)
    if ticker:
        stmt = stmt.where(PaperTrade.ticker == ticker.upper())
    stmt = stmt.order_by(PaperTrade.trade_date.desc(), PaperTrade.id.desc()).limit(limit)
    return list((await db.scalars(stmt)).all())


@router.get(
    "/portfolios/{portfolio_id}/performance",
    response_model=list[PaperPortfolioSnapshotOut],
)
async def portfolio_performance(
    portfolio_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=1_000)] = 365,
) -> list[PaperPortfolioSnapshot]:
    stmt = (
        select(PaperPortfolioSnapshot)
        .where(PaperPortfolioSnapshot.portfolio_id == portfolio_id)
        .order_by(PaperPortfolioSnapshot.snapshot_date.desc())
        .limit(limit)
    )
    return list((await db.scalars(stmt)).all())
