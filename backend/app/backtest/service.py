"""Veritabanindan tarihsel girdileri okuyup backtest sonucunu kalicilastirir."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.backtest.engine import (
    BacktestConfig,
    BacktestPrice,
    BacktestSignal,
    run_backtest,
)
from app.models import (
    BacktestRun,
    BacktestRunPoint,
    BacktestRunTrade,
    CompositeSignalSnapshot,
    PriceDaily,
)
from app.schemas.backtest import BacktestCreate

STRATEGY_VERSION = "backtest-v1"
SIGNAL_MODEL_VERSION = "v1"


def _decimal(value: float | Decimal) -> Decimal:
    return Decimal(str(value))


def backtest_status(*, signal_count: int, point_count: int, skipped_signal_count: int) -> str:
    has_executable_signal = signal_count > skipped_signal_count
    return "COMPLETED" if has_executable_signal and point_count >= 2 else "INSUFFICIENT_DATA"


async def create_backtest_run(session: AsyncSession, request: BacktestCreate) -> BacktestRun:
    signal_rows = list(
        (
            await session.scalars(
                select(CompositeSignalSnapshot)
                .where(
                    CompositeSignalSnapshot.model_version == SIGNAL_MODEL_VERSION,
                    CompositeSignalSnapshot.as_of_date >= request.start_date,
                    CompositeSignalSnapshot.as_of_date <= request.end_date,
                )
                .order_by(
                    CompositeSignalSnapshot.as_of_date,
                    CompositeSignalSnapshot.composite_score.desc(),
                    CompositeSignalSnapshot.ticker,
                )
            )
        ).all()
    )
    tickers = {row.ticker for row in signal_rows}
    price_rows = []
    if tickers:
        price_rows = list(
            (
                await session.scalars(
                    select(PriceDaily)
                    .where(
                        PriceDaily.ticker.in_(tickers),
                        PriceDaily.date >= request.start_date,
                        PriceDaily.date <= request.end_date,
                    )
                    .order_by(PriceDaily.date, PriceDaily.ticker)
                )
            ).all()
        )

    config = BacktestConfig(
        initial_cash=_decimal(request.initial_cash),
        entry_score=_decimal(request.entry_score),
        exit_score=_decimal(request.exit_score),
        min_confidence=_decimal(request.min_confidence),
        min_coverage=request.min_coverage,
        max_positions=request.max_positions,
        max_position_weight=_decimal(request.max_position_weight),
        fee_rate=_decimal(request.fee_rate),
        slippage_rate=_decimal(request.slippage_rate),
    )
    result = run_backtest(
        [
            BacktestSignal(
                ticker=row.ticker,
                signal_date=row.as_of_date,
                score=_decimal(row.composite_score),
                confidence=_decimal(row.confidence),
                coverage_count=row.coverage_count,
            )
            for row in signal_rows
        ],
        [
            BacktestPrice(
                ticker=row.ticker,
                price_date=row.date,
                close=_decimal(row.close),
            )
            for row in price_rows
        ],
        config=config,
    )
    metrics = result.metrics
    status = backtest_status(
        signal_count=len(signal_rows),
        point_count=len(result.points),
        skipped_signal_count=result.skipped_signals,
    )
    run = BacktestRun(
        strategy_version=STRATEGY_VERSION,
        signal_model_version=SIGNAL_MODEL_VERSION,
        status=status,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_cash=metrics.initial_cash,
        final_equity=metrics.final_equity,
        total_return_pct=metrics.total_return_pct,
        max_drawdown_pct=metrics.max_drawdown_pct,
        annualized_volatility_pct=metrics.annualized_volatility_pct,
        sharpe_ratio=metrics.sharpe_ratio,
        closed_trades=metrics.closed_trades,
        winning_trades=metrics.winning_trades,
        win_rate_pct=metrics.win_rate_pct,
        total_fees=metrics.total_fees,
        signal_count=len(signal_rows),
        price_count=len(price_rows),
        skipped_signal_count=result.skipped_signals,
        config={
            "entry_score": float(config.entry_score),
            "exit_score": float(config.exit_score),
            "min_confidence": float(config.min_confidence),
            "min_coverage": config.min_coverage,
            "max_positions": config.max_positions,
            "max_position_weight": float(config.max_position_weight),
            "fee_rate": float(config.fee_rate),
            "slippage_rate": float(config.slippage_rate),
            "execution_price": "NEXT_AVAILABLE_CLOSE",
            "risk_free_rate": 0,
        },
    )
    run.points = [
        BacktestRunPoint(
            point_date=point.point_date,
            cash=point.cash,
            positions_value=point.positions_value,
            total_equity=point.total_equity,
            position_count=point.position_count,
        )
        for point in result.points
    ]
    run.trades = [
        BacktestRunTrade(
            ticker=trade.ticker,
            side=trade.side,
            signal_date=trade.signal_date,
            execution_date=trade.execution_date,
            quantity=trade.quantity,
            price=trade.price,
            gross_amount=trade.gross_amount,
            fee_amount=trade.fee_amount,
            realized_pnl=trade.realized_pnl,
        )
        for trade in result.trades
    ]
    session.add(run)
    await session.commit()
    return await get_backtest_run(session, run.id)


async def get_backtest_run(session: AsyncSession, run_id: int) -> BacktestRun | None:
    return await session.scalar(
        select(BacktestRun)
        .options(selectinload(BacktestRun.points), selectinload(BacktestRun.trades))
        .where(BacktestRun.id == run_id)
    )
