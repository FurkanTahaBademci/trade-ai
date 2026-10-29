"""Paper portfoy, pozisyon, islem ve performans endpoint'leri.

Bu uclar yalniz herkese acik model portfoyu (`owner_id` bos) gosterir. Kullanici
portfoyleri `/api/me/portfolios` altindadir ve ayni sorgu yardimcilarini kullanir.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.csv_export import csv_response
from app.core.db import get_db
from app.core.sectors import resolve_sector
from app.models import Instrument, PaperPortfolio, PaperPortfolioSnapshot, PaperPosition, PaperTrade
from app.paper.risk import RiskConfig, compute_risk_metrics
from app.paper.service import load_risk_config, portfolio_strategy
from app.schemas.paper import (
    PaperPortfolioOut,
    PaperPortfolioSnapshotOut,
    PaperPositionOut,
    PaperRiskOut,
    PaperTradeOut,
)

router = APIRouter(prefix="/api/paper", tags=["paper-portfolio"])
DB = Annotated[AsyncSession, Depends(get_db)]
NOT_FOUND = "Paper portfoy bulunamadi"


async def public_portfolio(db: AsyncSession, portfolio_id: int) -> PaperPortfolio:
    portfolio = await db.get(PaperPortfolio, portfolio_id)
    if portfolio is None or portfolio.owner_id is not None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return portfolio


async def positions_of(
    db: AsyncSession, portfolio_id: int, ticker: str | None = None
) -> list[PaperPosition]:
    stmt = select(PaperPosition).where(PaperPosition.portfolio_id == portfolio_id)
    if ticker:
        stmt = stmt.where(PaperPosition.ticker == ticker.upper())
    stmt = stmt.order_by(PaperPosition.market_value.desc(), PaperPosition.ticker)
    return list((await db.scalars(stmt)).all())


async def trades_of(
    db: AsyncSession, portfolio_id: int, ticker: str | None = None, limit: int = 100
) -> list[PaperTrade]:
    stmt = select(PaperTrade).where(PaperTrade.portfolio_id == portfolio_id)
    if ticker:
        stmt = stmt.where(PaperTrade.ticker == ticker.upper())
    stmt = stmt.order_by(PaperTrade.trade_date.desc(), PaperTrade.id.desc()).limit(limit)
    return list((await db.scalars(stmt)).all())


def trades_csv(portfolio_id: int, trades: list[PaperTrade]):
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


async def performance_of(
    db: AsyncSession, portfolio_id: int, limit: int = 365
) -> list[PaperPortfolioSnapshot]:
    stmt = (
        select(PaperPortfolioSnapshot)
        .where(PaperPortfolioSnapshot.portfolio_id == portfolio_id)
        .order_by(PaperPortfolioSnapshot.snapshot_date.desc())
        .limit(limit)
    )
    return list((await db.scalars(stmt)).all())


async def risk_of(db: AsyncSession, portfolio: PaperPortfolio, cfg: RiskConfig | None) -> dict:
    """Risk metrikleri; `cfg` bos ise (manuel portfoy) kurallar kapali gosterilir."""
    positions = await positions_of(db, portfolio.id)
    snapshots = (
        await db.execute(
            select(PaperPortfolioSnapshot.snapshot_date, PaperPortfolioSnapshot.total_equity)
            .where(PaperPortfolioSnapshot.portfolio_id == portfolio.id)
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
    rules = cfg or RiskConfig(max_position_weight=0)
    return {
        "portfolio_id": portfolio.id,
        **metrics,
        "rules": {
            "stop_loss_pct": float(rules.stop_loss_pct),
            "take_profit_pct": float(rules.take_profit_pct),
            "trailing_stop_pct": float(rules.trailing_stop_pct),
            "max_position_weight_pct": float(rules.max_position_weight * 100),
            "max_sector_weight_pct": float(rules.max_sector_weight * 100),
            "rebalance_enabled": rules.rebalance_enabled,
        },
    }


@router.get("/portfolios", response_model=list[PaperPortfolioOut])
async def list_portfolios(db: DB) -> list[PaperPortfolio]:
    stmt = select(PaperPortfolio).where(PaperPortfolio.owner_id.is_(None))
    return list((await db.scalars(stmt.order_by(PaperPortfolio.id))).all())


@router.get("/portfolios/{portfolio_id}", response_model=PaperPortfolioOut)
async def get_portfolio(portfolio_id: int, db: DB) -> PaperPortfolio:
    return await public_portfolio(db, portfolio_id)


@router.get("/portfolios/{portfolio_id}/positions", response_model=list[PaperPositionOut])
async def list_positions(
    portfolio_id: int,
    db: DB,
    ticker: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
) -> list[PaperPosition]:
    await public_portfolio(db, portfolio_id)
    return await positions_of(db, portfolio_id, ticker)


@router.get("/portfolios/{portfolio_id}/trades", response_model=list[PaperTradeOut])
async def list_trades(
    portfolio_id: int,
    db: DB,
    ticker: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
    limit: Annotated[int, Query(ge=1, le=1_000)] = 100,
) -> list[PaperTrade]:
    await public_portfolio(db, portfolio_id)
    return await trades_of(db, portfolio_id, ticker, limit)


@router.get("/portfolios/{portfolio_id}/trades.csv")
async def export_trades_csv(
    portfolio_id: int,
    db: DB,
    ticker: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
):
    await public_portfolio(db, portfolio_id)
    return trades_csv(portfolio_id, await trades_of(db, portfolio_id, ticker, 1_000))


@router.get(
    "/portfolios/{portfolio_id}/performance",
    response_model=list[PaperPortfolioSnapshotOut],
)
async def portfolio_performance(
    portfolio_id: int,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=1_000)] = 365,
) -> list[PaperPortfolioSnapshot]:
    await public_portfolio(db, portfolio_id)
    return await performance_of(db, portfolio_id, limit)


@router.get("/portfolios/{portfolio_id}/risk", response_model=PaperRiskOut)
async def portfolio_risk(portfolio_id: int, db: DB) -> dict:
    portfolio = await public_portfolio(db, portfolio_id)
    _, cfg = portfolio_strategy(portfolio, await load_risk_config())
    return await risk_of(db, portfolio, cfg)
