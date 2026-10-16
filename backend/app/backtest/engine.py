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
from datetime import date, timedelta
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

MONEY_QUANTUM = Decimal("0.0001")
STRATEGIES = ("threshold", "basket")
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
    # 6 aylik walk-forward'da egitimin en iyi bes kombinasyonunun hepsi 55 kullandi.
    exit_score: Decimal = Decimal(55)
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
    # Gercekci yurutme: BIST'te tavanda kapanan hisse o kapanistan alinamaz,
    # tabanda kapanan satilamaz (kuyrukta kalir; satis sonraki gune kayar).
    price_limit_pct: Decimal = Decimal(0)
    # Son 20 islem gununun ortalama TL hacmi bunun altindaysa yeni pozisyon acilmaz.
    min_avg_volume: Decimal = Decimal(0)
    # XU100 bu kadar gunluk ortalamasinin altindayken yeni pozisyon acilmaz.
    regime_ma_days: int = 0
    # Son 20 islem gununun gunluk getiri std. sapmasi (%) bunu asan hisseye girilmez.
    max_volatility_pct: Decimal = Decimal(0)
    # "threshold": skor esiklerine gore gir/cik. "basket": her `rebalance_days`
    # islem gununde skoru en yuksek `basket_size` likit hisseyi esit agirlikla tut;
    # elde olan hisse ilk `basket_keep` icinde kaldikca satilmaz. Sepette giris/
    # cikis skoru, zarar-kes ve pozisyon sayisi/agirligi kullanilmaz.
    strategy: str = "threshold"
    basket_size: int = 20
    basket_keep: int = 40
    rebalance_days: int = 10

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
        if not (0 <= self.price_limit_pct < 100) or self.min_avg_volume < 0:
            raise ValueError("fiyat limiti ve hacim esigi gecersiz")
        if self.regime_ma_days < 0 or self.max_volatility_pct < 0:
            raise ValueError("rejim ortalamasi veya oynaklik siniri gecersiz")
        if self.strategy not in STRATEGIES:
            raise ValueError("strateji 'threshold' veya 'basket' olmali")
        if not (1 <= self.basket_size <= self.basket_keep) or self.rebalance_days < 1:
            raise ValueError("sepet boyutu, tutma esigi ve dengeleme araligi gecersiz")


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
    volume_try: Decimal | None = None


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


VOLUME_WINDOW = 20


def regime_is_bearish(
    benchmark_dates: list[date], benchmark_values: list[Decimal], day: date, window: int
) -> bool:
    """Endeksin `day` (dahil) itibariyla son kapanisi `window` gunluk ortalamasinin altinda mi?"""
    end = bisect_right(benchmark_dates, day)
    if window <= 0 or end < window:
        return False
    recent = benchmark_values[end - window : end]
    return recent[-1] < sum(recent, Decimal(0)) / window


@dataclass
class _Market:
    """Iki stratejinin ortak kullandigi, karar aninda bilinen piyasa verisi."""

    price_by_key: dict[tuple[date, str], Decimal]
    market_dates: list[date]
    closes_by_date: dict[date, list[tuple[str, Decimal]]]
    day_change: dict[tuple[date, str], Decimal]
    avg_volume: dict[tuple[date, str], Decimal]
    volatility: dict[tuple[date, str], float]
    warmup_prices: dict[str, Decimal]
    bench_dates: list[date]
    bench_values: list[Decimal]
    limit: Decimal

    def limit_up(self, day: date, ticker: str) -> bool:
        return self.limit > 0 and self.day_change.get((day, ticker), Decimal(0)) >= self.limit

    def limit_down(self, day: date, ticker: str) -> bool:
        return self.limit > 0 and self.day_change.get((day, ticker), Decimal(0)) <= -self.limit

    def bearish(self, day: date, window: int) -> bool:
        return regime_is_bearish(self.bench_dates, self.bench_values, day, window)


def _market(
    valid_prices: list[BacktestPrice],
    config: BacktestConfig,
    benchmark: list[tuple[date, Decimal]] | None,
    start_date: date | None,
) -> _Market:
    price_by_key = {
        (price.price_date, price.ticker): _decimal(price.close) for price in valid_prices
    }
    market_dates = sorted(
        {
            price.price_date
            for price in valid_prices
            if start_date is None or price.price_date >= start_date
        }
    )
    closes_by_date: dict[date, list[tuple[str, Decimal]]] = defaultdict(list)
    for (price_date, ticker), close in price_by_key.items():
        closes_by_date[price_date].append((ticker, close))
    # Hisse bazinda gunluk degisim (tavan/taban) ve 20 gunluk ortalama hacim.
    day_change: dict[tuple[date, str], Decimal] = {}
    avg_volume: dict[tuple[date, str], Decimal] = {}
    volatility: dict[tuple[date, str], float] = {}
    warmup_prices: dict[str, Decimal] = {}
    by_ticker: dict[str, list[BacktestPrice]] = defaultdict(list)
    for price in valid_prices:
        by_ticker[price.ticker].append(price)
    for ticker, rows in by_ticker.items():
        rows.sort(key=lambda row: row.price_date)
        volumes: list[Decimal] = []
        log_returns: list[float] = []
        for index, row in enumerate(rows):
            if start_date is not None and row.price_date < start_date:
                warmup_prices[ticker] = _decimal(row.close)
            if index:
                day_change[(row.price_date, ticker)] = (
                    _decimal(row.close) / _decimal(rows[index - 1].close) - 1
                ) * 100
            # Karar aninda bilinen hacim: islem gununden onceki 20 gun.
            window = volumes[-VOLUME_WINDOW:]
            if window:
                avg_volume[(row.price_date, ticker)] = sum(window, Decimal(0)) / len(window)
            recent = log_returns[-VOLUME_WINDOW:]
            if len(recent) == VOLUME_WINDOW:
                mean = sum(recent) / VOLUME_WINDOW
                variance = sum((value - mean) ** 2 for value in recent) / VOLUME_WINDOW
                volatility[(row.price_date, ticker)] = math.sqrt(variance) * 100
            volumes.append(_decimal(row.volume_try) if row.volume_try is not None else Decimal(0))
            if index:
                log_returns.append(math.log(float(row.close) / float(rows[index - 1].close)))
    bench_rows = sorted((day, _decimal(value)) for day, value in benchmark or [] if value)
    return _Market(
        price_by_key=price_by_key,
        market_dates=market_dates,
        closes_by_date=closes_by_date,
        day_change=day_change,
        avg_volume=avg_volume,
        volatility=volatility,
        warmup_prices=warmup_prices,
        bench_dates=[day for day, _ in bench_rows],
        bench_values=[value for _, value in bench_rows],
        limit=config.price_limit_pct,
    )


def _buy(
    ticker: str,
    close: Decimal,
    *,
    budget: Decimal,
    cash: Decimal,
    signal_date: date,
    market_date: date,
    config: BacktestConfig,
) -> tuple[_Position, BacktestTrade] | None:
    """Tam adetli alim plani (kayma + komisyon dahil); nakit yetmezse None."""
    execution_price = close * (Decimal(1) + config.slippage_rate)
    available = min(budget, cash)
    quantity = (available / (execution_price * (Decimal(1) + config.fee_rate))).to_integral_value(
        rounding=ROUND_FLOOR
    )
    if quantity <= 0:
        return None
    gross = _money(quantity * execution_price)
    fee = _money(gross * config.fee_rate)
    while quantity > 0 and gross + fee > cash:
        quantity -= 1
        gross = _money(quantity * execution_price)
        fee = _money(gross * config.fee_rate)
    if quantity <= 0 or gross < config.min_trade_value:
        return None
    trade = BacktestTrade(
        ticker=ticker,
        side="BUY",
        signal_date=signal_date,
        execution_date=market_date,
        quantity=quantity,
        price=execution_price,
        gross_amount=gross,
        fee_amount=fee,
    )
    return _Position(quantity, gross + fee), trade


def select_basket(ranked: list[str], *, held: set[str], size: int, keep: int) -> list[str]:
    """Sepet hedefi: ilk `keep` icinde kalan eldeki hisseler korunur, kalan yer
    sirali listeden doldurulur. Devir hizini (ve maliyeti) dusuk tutar."""
    keep_set = set(ranked[:keep])
    target = [ticker for ticker in ranked if ticker in held and ticker in keep_set][:size]
    for ticker in ranked:
        if len(target) >= size:
            break
        if ticker not in target:
            target.append(ticker)
    return target


def run_backtest(
    signals: list[BacktestSignal],
    prices: list[BacktestPrice],
    *,
    config: BacktestConfig | None = None,
    benchmark: list[tuple[date, Decimal]] | None = None,
    start_date: date | None = None,
) -> BacktestResult:
    """Long-only stratejiyi deterministik olarak calistir.

    Sinyal sonrasi fiyat bulunamayan veya izin verilen gecikmeyi asan satirlar
    `skipped_signals` sayacina girer. Acik pozisyonlar son bilinen kapanisla
    mark-to-market edilir; test sonunda varsayimsal satis yapilmaz.

    `start_date` verilirse daha onceki fiyatlar yalniz isinma (gunluk degisim,
    ortalama hacim) icin kullanilir; sermaye egrisi o gunden baslar.
    """

    active_config = config or BacktestConfig()
    valid_prices = [price for price in prices if price.close > 0]
    market = _market(valid_prices, active_config, benchmark, start_date)
    if active_config.strategy == "basket":
        return _run_basket(signals, market, active_config)
    price_by_key = market.price_by_key
    limit_up, limit_down = market.limit_up, market.limit_down
    avg_volume, volatility = market.avg_volume, market.volatility
    bench_dates, bench_values = market.bench_dates, market.bench_values
    events, skipped = _execution_events(
        signals, valid_prices, active_config.max_execution_delay_days
    )

    cash = _decimal(active_config.initial_cash)
    positions: dict[str, _Position] = {}
    last_prices: dict[str, Decimal] = {}
    trades: list[BacktestTrade] = []
    points: list[BacktestPoint] = []

    # Tabanda kaldigi icin satilamayan cikislar: hisse -> sinyal tarihi.
    pending_exits: dict[str, date | None] = {}
    last_prices.update(market.warmup_prices)

    for market_date in market.market_dates:
        for ticker, close in market.closes_by_date[market_date]:
            last_prices[ticker] = close

        event_rows = events.get(market_date, [])
        sold_today: set[str] = set()
        for ticker in sorted(pending_exits):
            close = price_by_key.get((market_date, ticker))
            if ticker not in positions:
                pending_exits.pop(ticker)
            elif close is not None and not limit_down(market_date, ticker):
                cash += _close_position(
                    trades,
                    positions,
                    ticker,
                    close,
                    market_date,
                    pending_exits.pop(ticker),
                    active_config,
                )
                sold_today.add(ticker)
        # Zarar-kes: paper portfoydeki gibi kapanis, ortalama maliyetin (komisyon
        # dahil) belirtilen yuzde altina indiyse o kapanista satilir.
        if active_config.stop_loss_pct > 0:
            for ticker in sorted(positions):
                position = positions[ticker]
                close = price_by_key.get((market_date, ticker))
                if close is None or position.quantity <= 0 or ticker in pending_exits:
                    continue
                average_cost = position.cost_basis / position.quantity
                if (close / average_cost - 1) * 100 > -active_config.stop_loss_pct:
                    continue
                if limit_down(market_date, ticker):
                    pending_exits[ticker] = None
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
            if signal.ticker in pending_exits:
                continue
            if limit_down(market_date, signal.ticker):
                pending_exits[signal.ticker] = signal.signal_date
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
            and not limit_up(market_date, signal.ticker)
            and avg_volume.get((market_date, signal.ticker), Decimal(0))
            >= active_config.min_avg_volume
            and (
                active_config.max_volatility_pct <= 0
                or volatility.get((market_date, signal.ticker), math.inf)
                <= float(active_config.max_volatility_pct)
            )
            and not regime_is_bearish(
                bench_dates, bench_values, signal.signal_date, active_config.regime_ma_days
            )
            and signal.score >= active_config.entry_score
            and signal.confidence >= active_config.min_confidence
            and signal.coverage_count >= active_config.min_coverage
            and (market_date, signal.ticker) in price_by_key
        ][:slots]
        budget = equity * active_config.max_position_weight
        for signal in eligible:
            planned = _buy(
                signal.ticker,
                price_by_key[(market_date, signal.ticker)],
                budget=budget,
                cash=cash,
                signal_date=signal.signal_date,
                market_date=market_date,
                config=active_config,
            )
            if planned is None:
                continue
            position, trade = planned
            cash -= position.cost_basis
            positions[signal.ticker] = position
            trades.append(trade)

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


def _run_basket(
    signals: list[BacktestSignal], market: _Market, config: BacktestConfig
) -> BacktestResult:
    """Siralama sepeti: her `rebalance_days` islem gununde hedef yeniden secilir.

    Hedef, islem gununden ONCEKI son skorlarla (en fazla `max_execution_delay_days`
    gun eski) secilir. Hedef disina dusen hisse satilir, hedefe giren hisse esit
    agirlikla alinir. Tabanda kapanan hisse satilamaz, tavanda kapanan alinamaz;
    bu islemler sonraki islem gunlerinde (bir sonraki dengelemeyi beklemeden)
    yeniden denenir.
    """
    ordered = sorted(signals, key=lambda row: (row.signal_date, row.ticker))
    latest: dict[str, BacktestSignal] = {}
    pointer = 0
    cash = _decimal(config.initial_cash)
    positions: dict[str, _Position] = {}
    last_prices: dict[str, Decimal] = dict(market.warmup_prices)
    trades: list[BacktestTrade] = []
    points: list[BacktestPoint] = []
    target: list[str] = []
    target_dates: dict[str, date] = {}

    for index, market_date in enumerate(market.market_dates):
        for ticker, close in market.closes_by_date[market_date]:
            last_prices[ticker] = close
        while pointer < len(ordered) and ordered[pointer].signal_date < market_date:
            latest[ordered[pointer].ticker] = ordered[pointer]
            pointer += 1

        if index % config.rebalance_days == 0:
            fresh = [
                row
                for row in latest.values()
                if (market_date - row.signal_date).days <= config.max_execution_delay_days
            ]
            bearish = config.regime_ma_days > 0 and market.bearish(
                market_date - timedelta(days=1), config.regime_ma_days
            )
            eligible = (
                []
                if bearish
                else [
                    row
                    for row in fresh
                    if row.confidence >= config.min_confidence
                    and row.coverage_count >= config.min_coverage
                    and (market_date, row.ticker) in market.price_by_key
                    and market.avg_volume.get((market_date, row.ticker), Decimal(0))
                    >= config.min_avg_volume
                    and (
                        config.max_volatility_pct <= 0
                        or market.volatility.get((market_date, row.ticker), math.inf)
                        <= float(config.max_volatility_pct)
                    )
                ]
            )
            ranked = [
                row.ticker for row in sorted(eligible, key=lambda row: (-row.score, row.ticker))
            ]
            target = select_basket(
                ranked, held=set(positions), size=config.basket_size, keep=config.basket_keep
            )
            target_dates = {row.ticker: row.signal_date for row in fresh}

        target_set = set(target)
        sold_today: set[str] = set()
        for ticker in sorted(positions):
            if ticker in target_set:
                continue
            close = market.price_by_key.get((market_date, ticker))
            if close is None or market.limit_down(market_date, ticker):
                continue  # islem yok / tabanda: sonraki gun yeniden denenir
            cash += _close_position(
                trades, positions, ticker, close, market_date, target_dates.get(ticker), config
            )
            sold_today.add(ticker)

        buyable = [
            ticker
            for ticker in target
            if ticker not in positions
            and ticker not in sold_today
            and (market_date, ticker) in market.price_by_key
            and not market.limit_up(market_date, ticker)
        ]
        if buyable and cash > 0:
            equity = cash + sum(
                (
                    position.quantity * last_prices.get(ticker, Decimal(0))
                    for ticker, position in positions.items()
                ),
                Decimal(0),
            )
            # Esit agirlik hedefi; nakit yetmezse yeni girenler arasinda esit bolunur.
            budget = min(equity / config.basket_size, cash / len(buyable))
            for ticker in buyable:
                planned = _buy(
                    ticker,
                    market.price_by_key[(market_date, ticker)],
                    budget=budget,
                    cash=cash,
                    signal_date=target_dates.get(ticker, market_date),
                    market_date=market_date,
                    config=config,
                )
                if planned is None:
                    continue
                position, trade = planned
                cash -= position.cost_basis
                positions[ticker] = position
                trades.append(trade)

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
        config=config,
        points=tuple(points),
        trades=tuple(trades),
        metrics=_metrics(config, points, trades),
        skipped_signals=0,
    )
