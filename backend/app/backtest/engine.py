"""Bilesik sinyalleri gecmis EOD fiyatlariyla degerlendirir.

Sinyaller ayni gunun kapanis verilerini de icerebildigi icin ayni gun isleme
girmez. Her sinyal yalniz ticker'in sonraki mevcut kapanisinda uygulanir. Veri
kaynagi acilis fiyati saglamadigindan bu varsayim acik ve muhafazakar tutulur.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

MONEY_QUANTUM = Decimal("0.0001")
PERCENT = Decimal(100)
TRADING_DAYS_PER_YEAR = Decimal(252)


def _decimal(value: Decimal | float | str) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: Decimal = Decimal(1_000_000)
    entry_score: Decimal = Decimal(75)
    exit_score: Decimal = Decimal(40)
    min_confidence: Decimal = Decimal("0.25")
    min_coverage: int = 2
    max_positions: int = 10
    max_position_weight: Decimal = Decimal("0.10")
    fee_rate: Decimal = Decimal("0.001")
    slippage_rate: Decimal = Decimal("0.0005")
    min_trade_value: Decimal = Decimal(1_000)
    max_execution_delay_days: int = 7
    # Paper portfoyle ayni risk kurallari; 0 kurali kapatir.
    stop_loss_pct: Decimal = Decimal(0)
    max_new_entries_per_day: int = 0

    def __post_init__(self) -> None:
        if self.initial_cash <= 0:
            raise ValueError("initial_cash sifirdan buyuk olmali")
        if not (0 <= self.exit_score < self.entry_score <= 100):
            raise ValueError("skor esikleri 0 <= exit < entry <= 100 olmali")
        if not (0 <= self.min_confidence <= 1):
            raise ValueError("min_confidence 0 ile 1 arasinda olmali")
        if self.min_coverage < 1 or self.max_positions < 1:
            raise ValueError("kapsam ve pozisyon limitleri pozitif olmali")
        if not (0 < self.max_position_weight <= 1):
            raise ValueError("max_position_weight 0 ile 1 arasinda olmali")
        if self.max_positions * self.max_position_weight > 1:
            raise ValueError("toplam hedef pozisyon agirligi 1'i asamaz")
        if self.fee_rate < 0 or not (0 <= self.slippage_rate < 1):
            raise ValueError("maliyet oranlari gecersiz")
        if self.min_trade_value < 0 or self.max_execution_delay_days < 1:
            raise ValueError("minimum islem ve gecikme limitleri gecersiz")
        if not (0 <= self.stop_loss_pct < 100) or self.max_new_entries_per_day < 0:
            raise ValueError("zarar-kes ve gunluk giris limiti gecersiz")


@dataclass(frozen=True)
class BacktestSignal:
    ticker: str
    signal_date: date
    score: Decimal
    confidence: Decimal
    coverage_count: int


@dataclass(frozen=True)
class BacktestPrice:
    ticker: str
    price_date: date
    close: Decimal


@dataclass(frozen=True)
class BacktestTrade:
    ticker: str
    side: str
    signal_date: date
    execution_date: date
    quantity: Decimal
    price: Decimal
    gross_amount: Decimal
    fee_amount: Decimal
    realized_pnl: Decimal | None = None


@dataclass(frozen=True)
class BacktestPoint:
    point_date: date
    cash: Decimal
    positions_value: Decimal
    total_equity: Decimal
    position_count: int


@dataclass(frozen=True)
class BacktestMetrics:
    initial_cash: Decimal
    final_equity: Decimal
    total_return_pct: Decimal
    max_drawdown_pct: Decimal
    annualized_volatility_pct: Decimal | None
    sharpe_ratio: Decimal | None
    closed_trades: int
    winning_trades: int
    win_rate_pct: Decimal | None
    total_fees: Decimal


@dataclass(frozen=True)
class BacktestResult:
    config: BacktestConfig
    points: tuple[BacktestPoint, ...]
    trades: tuple[BacktestTrade, ...]
    metrics: BacktestMetrics
    skipped_signals: int


@dataclass
class _Position:
    quantity: Decimal
    cost_basis: Decimal


def _close_position(
    trades: list[BacktestTrade],
    positions: dict[str, _Position],
    ticker: str,
    close: Decimal,
    market_date: date,
    signal_date: date | None,
    config: BacktestConfig,
) -> Decimal:
    """Pozisyonu kapanista (olumsuz kaymayla) satar; nakde eklenecek net tutari doner."""
    position = positions.pop(ticker)
    execution_price = close * (Decimal(1) - config.slippage_rate)
    gross = _money(position.quantity * execution_price)
    fee = _money(gross * config.fee_rate)
    trades.append(
        BacktestTrade(
            ticker=ticker,
            side="SELL",
            signal_date=signal_date or market_date,
            execution_date=market_date,
            quantity=position.quantity,
            price=execution_price,
            gross_amount=gross,
            fee_amount=fee,
            realized_pnl=_money(gross - fee - position.cost_basis),
        )
    )
    return gross - fee


def _execution_events(
    signals: list[BacktestSignal], prices: list[BacktestPrice], max_delay_days: int
) -> tuple[dict[date, list[BacktestSignal]], int]:
    ticker_dates: dict[str, list[date]] = defaultdict(list)
    for price in prices:
        if price.close > 0:
            ticker_dates[price.ticker].append(price.price_date)
    for dates in ticker_dates.values():
        dates.sort()

    events: dict[date, dict[str, BacktestSignal]] = defaultdict(dict)
    skipped = 0
    for signal in sorted(signals, key=lambda row: (row.signal_date, row.ticker)):
        dates = ticker_dates.get(signal.ticker, [])
        # Sinyal gununden sonraki ilk islem gunu (ikili arama; dogrusal tarama
        # uzun araliklarda sinyal x fiyat gunu kadar yineleme yapiyordu).
        index = bisect_right(dates, signal.signal_date)
        execution_date = dates[index] if index < len(dates) else None
        if (
            execution_date is not None
            and (execution_date - signal.signal_date).days > max_delay_days
        ):
            execution_date = None
        if execution_date is None:
            skipped += 1
            continue
        current = events[execution_date].get(signal.ticker)
        if current is None or current.signal_date < signal.signal_date:
            events[execution_date][signal.ticker] = signal

    return {
        event_date: sorted(rows.values(), key=lambda row: (-row.score, row.ticker))
        for event_date, rows in events.items()
    }, skipped


def _metrics(
    config: BacktestConfig, points: list[BacktestPoint], trades: list[BacktestTrade]
) -> BacktestMetrics:
    final_equity = points[-1].total_equity if points else config.initial_cash
    total_return = (final_equity / config.initial_cash - 1) * PERCENT

    peak = config.initial_cash
    max_drawdown = Decimal(0)
    returns: list[float] = []
    previous = config.initial_cash
    for point in points:
        peak = max(peak, point.total_equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - point.total_equity) / peak)
        if previous > 0 and point.total_equity != previous:
            returns.append(float(point.total_equity / previous - 1))
        elif previous > 0:
            returns.append(0.0)
        previous = point.total_equity

    volatility: Decimal | None = None
    sharpe: Decimal | None = None
    if len(returns) >= 2:
        mean = sum(returns) / len(returns)
        variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
        daily_std = math.sqrt(variance)
        volatility = _decimal(daily_std * math.sqrt(float(TRADING_DAYS_PER_YEAR)) * 100)
        if daily_std > 0:
            sharpe = _decimal(mean / daily_std * math.sqrt(float(TRADING_DAYS_PER_YEAR)))

    closed = [trade for trade in trades if trade.side == "SELL"]
    winning = sum(1 for trade in closed if (trade.realized_pnl or Decimal(0)) > 0)
    win_rate = _decimal(winning / len(closed) * 100) if closed else None
    return BacktestMetrics(
        initial_cash=_money(config.initial_cash),
        final_equity=_money(final_equity),
        total_return_pct=total_return.quantize(Decimal("0.0001")),
        max_drawdown_pct=(max_drawdown * PERCENT).quantize(Decimal("0.0001")),
        annualized_volatility_pct=(
            volatility.quantize(Decimal("0.0001")) if volatility is not None else None
        ),
        sharpe_ratio=sharpe.quantize(Decimal("0.0001")) if sharpe is not None else None,
        closed_trades=len(closed),
        winning_trades=winning,
        win_rate_pct=win_rate.quantize(Decimal("0.0001")) if win_rate is not None else None,
        total_fees=_money(sum((trade.fee_amount for trade in trades), Decimal(0))),
    )


def run_backtest(
    signals: list[BacktestSignal],
    prices: list[BacktestPrice],
    *,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Long-only stratejiyi deterministik olarak calistir.

    Sinyal sonrasi fiyat bulunamayan veya izin verilen gecikmeyi asan satirlar
    `skipped_signals` sayacina girer. Acik pozisyonlar son bilinen kapanisla
    mark-to-market edilir; test sonunda varsayimsal satis yapilmaz.
    """

    active_config = config or BacktestConfig()
    valid_prices = [price for price in prices if price.close > 0]
    price_by_key = {
        (price.price_date, price.ticker): _decimal(price.close) for price in valid_prices
    }
    market_dates = sorted({price.price_date for price in valid_prices})
    closes_by_date: dict[date, list[tuple[str, Decimal]]] = defaultdict(list)
    for (price_date, ticker), close in price_by_key.items():
        closes_by_date[price_date].append((ticker, close))
    events, skipped = _execution_events(
        signals, valid_prices, active_config.max_execution_delay_days
    )

    cash = _decimal(active_config.initial_cash)
    positions: dict[str, _Position] = {}
    last_prices: dict[str, Decimal] = {}
    trades: list[BacktestTrade] = []
    points: list[BacktestPoint] = []

    for market_date in market_dates:
        for ticker, close in closes_by_date[market_date]:
            last_prices[ticker] = close

        event_rows = events.get(market_date, [])
        sold_today: set[str] = set()
        # Zarar-kes: paper portfoydeki gibi kapanis, ortalama maliyetin (komisyon
        # dahil) belirtilen yuzde altina indiyse o kapanista satilir.
        if active_config.stop_loss_pct > 0:
            for ticker in sorted(positions):
                position = positions[ticker]
                close = price_by_key.get((market_date, ticker))
                if close is None or position.quantity <= 0:
                    continue
                average_cost = position.cost_basis / position.quantity
                if (close / average_cost - 1) * 100 > -active_config.stop_loss_pct:
                    continue
                cash += _close_position(
                    trades, positions, ticker, close, market_date, None, active_config
                )
                sold_today.add(ticker)
        for signal in sorted(event_rows, key=lambda row: row.ticker):
            position = positions.get(signal.ticker)
            close = price_by_key.get((market_date, signal.ticker))
            if position is None or close is None or signal.score >= active_config.exit_score:
                continue
            cash += _close_position(
                trades,
                positions,
                signal.ticker,
                close,
                market_date,
                signal.signal_date,
                active_config,
            )
            sold_today.add(signal.ticker)

        positions_value = sum(
            (
                position.quantity * last_prices.get(ticker, Decimal(0))
                for ticker, position in positions.items()
            ),
            Decimal(0),
        )
        equity = cash + positions_value
        slots = active_config.max_positions - len(positions)
        if active_config.max_new_entries_per_day > 0:
            slots = min(slots, active_config.max_new_entries_per_day)
        eligible = [
            signal
            for signal in event_rows
            if signal.ticker not in positions
            and signal.ticker not in sold_today
            and signal.score >= active_config.entry_score
            and signal.confidence >= active_config.min_confidence
            and signal.coverage_count >= active_config.min_coverage
            and (market_date, signal.ticker) in price_by_key
        ][:slots]
        budget = equity * active_config.max_position_weight
        for signal in eligible:
            close = price_by_key[(market_date, signal.ticker)]
            execution_price = close * (Decimal(1) + active_config.slippage_rate)
            available = min(budget, cash)
            quantity = (
                available / (execution_price * (Decimal(1) + active_config.fee_rate))
            ).to_integral_value(rounding=ROUND_FLOOR)
            if quantity <= 0:
                continue
            gross = _money(quantity * execution_price)
            fee = _money(gross * active_config.fee_rate)
            while quantity > 0 and gross + fee > cash:
                quantity -= 1
                gross = _money(quantity * execution_price)
                fee = _money(gross * active_config.fee_rate)
            if quantity <= 0 or gross < active_config.min_trade_value:
                continue
            cash -= gross + fee
            positions[signal.ticker] = _Position(quantity, gross + fee)
            trades.append(
                BacktestTrade(
                    ticker=signal.ticker,
                    side="BUY",
                    signal_date=signal.signal_date,
                    execution_date=market_date,
                    quantity=quantity,
                    price=execution_price,
                    gross_amount=gross,
                    fee_amount=fee,
                )
            )

        positions_value = sum(
            (
                position.quantity * last_prices.get(ticker, Decimal(0))
                for ticker, position in positions.items()
            ),
            Decimal(0),
        )
        points.append(
            BacktestPoint(
                point_date=market_date,
                cash=_money(cash),
                positions_value=_money(positions_value),
                total_equity=_money(cash + positions_value),
                position_count=len(positions),
            )
        )

    return BacktestResult(
        config=active_config,
        points=tuple(points),
        trades=tuple(trades),
        metrics=_metrics(active_config, points, trades),
        skipped_signals=skipped,
    )
