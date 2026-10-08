"""Paper portfoy, pozisyon, islem ve performans endpoint'leri."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.csv_export import csv_response
from app.core.db import get_db
from app.core.sectors import resolve_sector
from app.models import Instrument, PaperPortfolio, PaperPortfolioSnapshot, PaperPosition, PaperTrade
from app.paper.risk import compute_risk_metrics
from app.paper.service import load_risk_config
from app.schemas.paper import (
    PaperPortfolioOut,
    PaperPortfolioSnapshotOut,
    PaperPositionOut,
    PaperRiskOut,
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


@router.get("/portfolios/{portfolio_id}/trades.csv")
async def export_trades_csv(
    portfolio_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    ticker: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
):
    if await db.get(PaperPortfolio, portfolio_id) is None:
        raise HTTPException(status_code=404, detail="Paper portfoy bulunamadi")
    trades = await list_trades(portfolio_id=portfolio_id, db=db, ticker=ticker, limit=1_000)
    return csv_response(
        f"paper-islemler-{portfolio_id}.csv",
        [
            "Tarih",
            "Hisse",
            "Yön",
            "Adet",
            "Fiyat",
            "Tutar",
            "Komisyon",
            "Gerçekleşen K/Z",
            "Strateji",
            "Gerekçe",
        ],
        [
            (
                t.trade_date,
                t.ticker,
                t.side,
                t.quantity,
                t.price,
                t.gross_amount,
                t.fee_amount,
                t.realized_pnl,
                t.strategy_version,
                t.reason,
            )
            for t in trades
        ],
    )


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


@router.get("/portfolios/{portfolio_id}/risk", response_model=PaperRiskOut)
async def portfolio_risk(
    portfolio_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict:
    portfolio = await db.get(PaperPortfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Paper portfoy bulunamadi")
    positions = list(
        (
            await db.scalars(
                select(PaperPosition).where(PaperPosition.portfolio_id == portfolio_id)
            )
        ).all()
    )
    snapshots = (
        await db.execute(
            select(PaperPortfolioSnapshot.snapshot_date, PaperPortfolioSnapshot.total_equity)
            .where(PaperPortfolioSnapshot.portfolio_id == portfolio_id)
            .order_by(PaperPortfolioSnapshot.snapshot_date)
        )
    ).all()
    names = dict(
        (
            await db.execute(
                select(Instrument.ticker, Instrument.name).where(
                    Instrument.ticker.in_([row.ticker for row in positions])
                )
            )
        ).all()
    )
    metrics = compute_risk_metrics(
        equity_series=[(row.snapshot_date, float(row.total_equity)) for row in snapshots],
        position_values={row.ticker: float(row.market_value) for row in positions},
        cash=float(portfolio.cash_balance),
        sector_of=lambda ticker: resolve_sector(ticker, names.get(ticker)),
    )
    cfg = await load_risk_config()
    return {
        "portfolio_id": portfolio_id,
        **metrics,
        "rules": {
            "stop_loss_pct": float(cfg.stop_loss_pct),
            "take_profit_pct": float(cfg.take_profit_pct),
            "trailing_stop_pct": float(cfg.trailing_stop_pct),
            "max_position_weight_pct": float(cfg.max_position_weight * 100),
            "max_sector_weight_pct": float(cfg.max_sector_weight * 100),
            "rebalance_enabled": cfg.rebalance_enabled,
        },
    }
