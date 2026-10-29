"""Backtest kosularini kuyruga yazar; worker'da tarihsel girdileri okuyup sonucu kalicilastirir."""

import asyncio
import statistics
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

from app.backtest.engine import (
    BacktestConfig,
    BacktestPrice,
    BacktestResult,
    BacktestSignal,
    run_backtest,
)
from app.core.config import get_settings
from app.models import (
    BacktestRun,
    BacktestRunPoint,
    BacktestRunTrade,
    CompositeSignalSnapshot,
    IndexDaily,
    PriceDaily,
)
from app.schemas.backtest import BacktestCreate
from app.signals.service import BENCHMARK_INDEX, recombine_score
from app.signals.service import MODEL_VERSION as SIGNAL_MODEL_VERSION

# v2: paper portfoyle ayni zarar-kes ve gunluk yeni pozisyon siniri.
# v3: tavan/taban yurutme kurali, likidite esigi ve istege bagli rejim filtresi.
# v4: siralama sepeti stratejisi, agirlik simulasyonu, varsayilan cikis skoru 55
# ve baslangic gunu hassasiyeti.
STRATEGY_VERSION = "backtest-v4"
# Gunluk degisim ve 20 gunluk ortalama hacim icin baslangictan onceki fiyatlar.
WARMUP_DAYS = 45
# Hassasiyet kosulari: baslangic bu kadar islem gunu kaydirilarak tekrarlanir.
ROBUSTNESS_SHIFTS = (2, 4, 6, 8)
# Daha uzun araliklarda ek kosular istegi gereksiz uzatir; hassasiyet atlanir.
ROBUSTNESS_MAX_DAYS = 3 * 365
# Bu sureden uzun QUEUED/RUNNING kalan kosu (worker yeniden baslatildi vb.) hatayla kapanir.
STALE_AFTER = timedelta(hours=2)

logger = structlog.get_logger(__name__)


def _decimal(value: float | Decimal) -> Decimal:
    return Decimal(str(value))


def backtest_status(*, signal_count: int, point_count: int, skipped_signal_count: int) -> str:
    has_executable_signal = signal_count > skipped_signal_count
    return "COMPLETED" if has_executable_signal and point_count >= 2 else "INSUFFICIENT_DATA"


def _benchmark_return(
    benchmark: list[tuple[date, Decimal]], first: date, last: date
) -> float | None:
    """XU100'un `first` ve `last` gunlerindeki (veya oncesindeki son) kapanislara gore getirisi."""

    def value_on(day: date) -> Decimal | None:
        values = [value for point_date, value in benchmark if point_date <= day]
        return values[-1] if values else None

    start_value, end_value = value_on(first), value_on(last)
    if not start_value or not end_value:
        return None
    return float((end_value / start_value - 1) * 100)


def _summary(result: BacktestResult, benchmark: list[tuple[date, Decimal]]) -> dict[str, Any]:
    first, last = result.points[0].point_date, result.points[-1].point_date
    total = float(result.metrics.total_return_pct)
    bench = _benchmark_return(benchmark, first, last)
    return {
        "start_date": first.isoformat(),
        "total_return_pct": round(total, 4),
        "benchmark_return_pct": round(bench, 4) if bench is not None else None,
        "excess_return_pct": round(total - bench, 4) if bench is not None else None,
    }


def run_with_robustness(
    signals: list[BacktestSignal],
    prices: list[BacktestPrice],
    *,
    config: BacktestConfig,
    benchmark: list[tuple[date, Decimal]],
    start_date: date,
    end_date: date,
) -> tuple[BacktestResult, dict[str, Any] | None]:
    """Ana kosu + baslangici birkac islem gunu kaydirilmis ek kosular.

    Siralama sepetinde dengeleme takvimi, esik stratejisinde giris zamanlari
    baslangica baglidir; 6 aylik veride yalniz birkac gunluk kayma XU100'e gore
    sonucu +7 ile -8 puan arasinda oynatti. Tek kosu yerine dagilim raporlanir.
    """
    result = run_backtest(
        signals, prices, config=config, benchmark=benchmark, start_date=start_date
    )
    if len(result.points) < 2 or (end_date - start_date).days > ROBUSTNESS_MAX_DAYS:
        return result, None
    market_dates = [point.point_date for point in result.points]
    runs = [_summary(result, benchmark)]
    for shift in ROBUSTNESS_SHIFTS:
        if shift >= len(market_dates) - 1:
            break
        shifted = run_backtest(
            signals,
            prices,
            config=config,
            benchmark=benchmark,
            start_date=market_dates[shift],
        )
        if len(shifted.points) >= 2:
            runs.append(_summary(shifted, benchmark))
    excess = [run["excess_return_pct"] for run in runs if run["excess_return_pct"] is not None]
    return result, {
        "shifts_trading_days": [0, *ROBUSTNESS_SHIFTS][: len(runs)],
        "runs": runs,
        "excess_mean_pct": round(statistics.mean(excess), 4) if excess else None,
        "excess_min_pct": round(min(excess), 4) if excess else None,
        "excess_max_pct": round(max(excess), 4) if excess else None,
        "beat_benchmark_runs": sum(value > 0 for value in excess),
    }


async def _compute(session: AsyncSession, run: BacktestRun, request: BacktestCreate) -> None:
    """Girdileri okur, motoru ayri thread'de kosar ve sonucu `run` satirina yazar."""
    weights = (
        {name: _decimal(value) for name, value in request.component_weights.items()}
        if request.component_weights
        else None
    )
    # Yalniz strateji kolonlari okunur; kanit (evidence) JSON'unun tamami cekilmez.
    columns = [
        CompositeSignalSnapshot.ticker,
        CompositeSignalSnapshot.as_of_date,
        CompositeSignalSnapshot.composite_score,
        CompositeSignalSnapshot.confidence,
        CompositeSignalSnapshot.coverage_count,
    ]
    if weights:
        columns += [
            CompositeSignalSnapshot.component_scores,
            CompositeSignalSnapshot.evidence["confidences"].label("component_confidences"),
        ]
    signal_rows = (
        await session.execute(
            select(*columns)
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
    signals: list[BacktestSignal] = []
    for row in signal_rows:
        score = (
            recombine_score(
                row.component_scores or {},
                weights,
                confidence=_decimal(row.confidence),
                component_confidences=row.component_confidences,
            )
            if weights
            else _decimal(row.composite_score)
        )
        if score is not None:
            signals.append(
                BacktestSignal(
                    ticker=row.ticker,
                    signal_date=row.as_of_date,
                    score=score,
                    confidence=_decimal(row.confidence),
                    coverage_count=row.coverage_count,
                )
            )
    tickers = {row.ticker for row in signal_rows}
    price_rows = []
    if tickers:
        price_rows = (
            await session.execute(
                select(PriceDaily.ticker, PriceDaily.date, PriceDaily.close, PriceDaily.volume_try)
                .where(
                    PriceDaily.ticker.in_(tickers),
                    PriceDaily.date >= request.start_date - timedelta(days=WARMUP_DAYS),
                    PriceDaily.date <= request.end_date,
                )
                .order_by(PriceDaily.date, PriceDaily.ticker)
            )
        ).all()

    # XU100: rejim filtresi ve hassasiyet kosularinin endekse gore sonucu icin.
    benchmark: list[tuple[date, Decimal]] = [
        (row.date, _decimal(row.value))
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
        if row.value
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
        strategy=request.strategy,
        basket_size=request.basket_size,
        basket_keep=request.basket_keep,
        rebalance_days=request.rebalance_days,
    )
    # Saf ve CPU yogun hesap: olay dongusunu (tek uvicorn sureci) bloklamasin diye
    # ayri thread'de calisir; aksi halde uzun bir test suresince tum API yanit vermez.
    result, robustness = await asyncio.to_thread(
        run_with_robustness,
        signals,
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
        end_date=request.end_date,
    )
    metrics = result.metrics
    status = backtest_status(
        signal_count=len(signals),
        point_count=len(result.points),
        skipped_signal_count=result.skipped_signals,
    )
    run.status = status
    run.strategy_version = STRATEGY_VERSION
    run.signal_model_version = SIGNAL_MODEL_VERSION
    run.initial_cash = metrics.initial_cash
    run.final_equity = metrics.final_equity
    run.total_return_pct = metrics.total_return_pct
    run.max_drawdown_pct = metrics.max_drawdown_pct
    run.annualized_volatility_pct = metrics.annualized_volatility_pct
    run.sharpe_ratio = metrics.sharpe_ratio
    run.closed_trades = metrics.closed_trades
    run.winning_trades = metrics.winning_trades
    run.win_rate_pct = metrics.win_rate_pct
    run.total_fees = metrics.total_fees
    run.signal_count = len(signals)
    run.price_count = in_range_prices
    run.skipped_signal_count = result.skipped_signals
    run.robustness = robustness
    run.config = {
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
        "strategy": config.strategy,
        "basket_size": config.basket_size,
        "basket_keep": config.basket_keep,
        "rebalance_days": config.rebalance_days,
        "component_weights": (
            {name: float(value) for name, value in weights.items()} if weights else None
        ),
        "execution_price": "NEXT_AVAILABLE_CLOSE",
        "risk_free_rate": 0,
    }
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


def request_config(request: BacktestCreate) -> dict[str, Any]:
    """Kuyruktaki kosunun ayarlari; worker bunlardan `BacktestCreate`'i yeniden kurar."""
    return request.model_dump(mode="json", exclude={"start_date", "end_date", "initial_cash"})


def stored_request(run: BacktestRun) -> BacktestCreate:
    return BacktestCreate.model_validate(
        {
            **(run.config or {}),
            "start_date": run.start_date,
            "end_date": run.end_date,
            "initial_cash": float(run.initial_cash),
        }
    )


async def fail_stale_runs(session: AsyncSession) -> int:
    """Worker yeniden baslatildiginda vb. takili kalan kosulari hatayla kapatir."""
    cutoff = datetime.now(UTC) - STALE_AFTER
    result = await session.execute(
        update(BacktestRun)
        .where(BacktestRun.status.in_(("QUEUED", "RUNNING")), BacktestRun.created_at < cutoff)
        .values(status="FAILED", error="Koşu zaman aşımına uğradı; yeniden başlatın.")
    )
    return result.rowcount or 0


async def _enqueue(run_id: int) -> bool:
    try:
        pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    except Exception as exc:  # noqa: BLE001 - kosu FAILED isaretlenir
        logger.error("backtest_enqueue_failed", run_id=run_id, error=str(exc))
        return False
    try:
        await pool.enqueue_job("run_backtest", run_id, _job_id=f"backtest:{run_id}")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("backtest_enqueue_failed", run_id=run_id, error=str(exc))
        return False
    finally:
        await pool.aclose()


async def queue_backtest_run(
    session: AsyncSession, request: BacktestCreate, *, owner_id: int | None
) -> BacktestRun:
    """Kosuyu QUEUED yazar ve worker kuyruguna ekler; hesap worker'da yapilir."""
    await fail_stale_runs(session)
    run = BacktestRun(
        owner_id=owner_id,
        strategy_version=STRATEGY_VERSION,
        signal_model_version=SIGNAL_MODEL_VERSION,
        status="QUEUED",
        start_date=request.start_date,
        end_date=request.end_date,
        initial_cash=_decimal(request.initial_cash),
        config=request_config(request),
    )
    session.add(run)
    await session.commit()
    if not await _enqueue(run.id):
        run.status = "FAILED"
        run.error = "Koşu kuyruğa eklenemedi; biraz sonra yeniden deneyin."
        await session.commit()
    return await get_backtest_run(session, run.id)


async def execute_backtest_run(session: AsyncSession, run_id: int) -> dict[str, Any]:
    """Worker isi: kuyruktaki kosuyu hesaplar. Bitmis ya da silinmis kosuyu atlar."""
    # Nokta/islem koleksiyonlari yuklu olmali: atama async oturumda tembel yukleme yapamaz.
    run = await get_backtest_run(session, run_id)
    if run is None or run.status not in ("QUEUED", "RUNNING"):
        return {"run_id": run_id, "status": run.status if run else "missing"}
    run.status = "RUNNING"
    run.started_at = datetime.now(UTC)
    run.error = None
    await session.commit()
    try:
        await _compute(session, run, stored_request(run))
        run.finished_at = datetime.now(UTC)
        await session.commit()
        return {"run_id": run_id, "status": run.status, "trades": len(run.trades)}
    except Exception as exc:  # kosu hata mesajiyla kapanir
        await session.rollback()
        logger.exception("backtest_failed", run_id=run_id)
        await session.execute(
            update(BacktestRun)
            .where(BacktestRun.id == run_id)
            .values(
                status="FAILED",
                error=f"Koşu hesaplanamadı: {exc}"[:500],
                finished_at=datetime.now(UTC),
            )
        )
        await session.commit()
        return {"run_id": run_id, "status": "FAILED"}


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
