"""Veritabanindan tarihsel girdileri okuyup backtest sonucunu kalicilastirir."""

import asyncio
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

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
    IndexDaily,
    PriceDaily,
)
from app.schemas.backtest import BacktestCreate
from app.signals.service import BENCHMARK_INDEX
from app.signals.service import MODEL_VERSION as SIGNAL_MODEL_VERSION

# v2: paper portfoyle ayni zarar-kes ve gunluk yeni pozisyon siniri.
# v3: tavan/taban yurutme kurali, likidite esigi ve istege bagli rejim filtresi.
STRATEGY_VERSION = "backtest-v3"
# Gunluk degisim ve 20 gunluk ortalama hacim icin baslangictan onceki fiyatlar.
WARMUP_DAYS = 45


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
                        PriceDaily.date >= request.start_date - timedelta(days=WARMUP_DAYS),
                        PriceDaily.date <= request.end_date,
                    )
                    .order_by(PriceDaily.date, PriceDaily.ticker)
                )
            ).all()
        )

    benchmark: list[tuple] = []
    if request.regime_ma_days > 0:
        benchmark = [
            (row.date, row.value)
            for row in (
                await session.execute(
                    select(IndexDaily.date, IndexDaily.value)
                    .where(
                        IndexDaily.index_code == BENCHMARK_INDEX,
                        # Islem gunu ~ takvim gununun 5/7'si; ortalama icin bol pay.
                        IndexDaily.date
                        >= request.start_date - timedelta(days=request.regime_ma_days * 2 + 10),
                        IndexDaily.date <= request.end_date,
                    )
                    .order_by(IndexDaily.date)
                )
            ).all()
        ]
    in_range_prices = sum(1 for row in price_rows if row.date >= request.start_date)

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
        stop_loss_pct=_decimal(request.stop_loss_pct),
        max_new_entries_per_day=request.max_new_entries_per_day,
        price_limit_pct=_decimal(request.price_limit_pct),
        min_avg_volume=_decimal(request.min_avg_volume),
        regime_ma_days=request.regime_ma_days,
        max_volatility_pct=_decimal(request.max_volatility_pct),
    )
    # Saf ve CPU yogun hesap: olay dongusunu (tek uvicorn sureci) bloklamasin diye
    # ayri thread'de calisir; aksi halde uzun bir test suresince tum API yanit vermez.
    result = await asyncio.to_thread(
        run_backtest,
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
                volume_try=_decimal(row.volume_try) if row.volume_try is not None else None,
            )
            for row in price_rows
        ],
        config=config,
        benchmark=benchmark,
        start_date=request.start_date,
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
        price_count=in_range_prices,
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
            "stop_loss_pct": float(config.stop_loss_pct),
            "max_new_entries_per_day": config.max_new_entries_per_day,
            "price_limit_pct": float(config.price_limit_pct),
            "min_avg_volume": float(config.min_avg_volume),
            "regime_ma_days": config.regime_ma_days,
            "max_volatility_pct": float(config.max_volatility_pct),
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


async def get_backtest_run(
    session: AsyncSession, run_id: int, *, include_trades: bool = True
) -> BacktestRun | None:
    return await session.scalar(
        select(BacktestRun)
        .options(
            selectinload(BacktestRun.points),
            selectinload(BacktestRun.trades) if include_trades else noload(BacktestRun.trades),
        )
        .where(BacktestRun.id == run_id)
    )
