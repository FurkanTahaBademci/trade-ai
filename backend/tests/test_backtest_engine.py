"""Noktasal-zaman uyumlu backtest motoru testleri."""

from datetime import date
from decimal import Decimal

from app.backtest import BacktestConfig, BacktestPrice, BacktestSignal, run_backtest


def signal(
    ticker: str,
    day: int,
    score: str,
    *,
    confidence: str = "0.80",
    coverage: int = 4,
) -> BacktestSignal:
    return BacktestSignal(
        ticker=ticker,
        signal_date=date(2026, 1, day),
        score=Decimal(score),
        confidence=Decimal(confidence),
        coverage_count=coverage,
    )


def price(ticker: str, day: int, close: str) -> BacktestPrice:
    return BacktestPrice(ticker, date(2026, 1, day), Decimal(close))


def test_signal_executes_only_at_next_available_close():
    result = run_backtest(
        [signal("THYAO", 2, "80")],
        [price("THYAO", 2, "100"), price("THYAO", 5, "110")],
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.signal_date == date(2026, 1, 2)
    assert trade.execution_date == date(2026, 1, 5)
    assert trade.price == Decimal(110) * (Decimal(1) + result.config.slippage_rate)


def test_signal_without_a_timely_future_price_is_skipped():
    result = run_backtest(
        [signal("THYAO", 2, "80")],
        [price("THYAO", 2, "100"), price("THYAO", 12, "110")],
    )

    assert result.trades == ()
    assert result.skipped_signals == 1


def test_entry_filters_and_position_limit_are_applied_in_score_order():
    signals = [
        signal("AAAA", 2, "80"),
        signal("BBBB", 2, "90"),
        signal("CCCC", 2, "95", confidence="0.10"),
        signal("DDDD", 2, "70"),
    ]
    prices = [price(ticker, 5, "100") for ticker in ("AAAA", "BBBB", "CCCC", "DDDD")]

    result = run_backtest(signals, prices, config=BacktestConfig(max_positions=1))

    assert [(trade.ticker, trade.side) for trade in result.trades] == [("BBBB", "BUY")]


def test_exit_signal_sells_on_following_trading_day_and_records_realized_pnl():
    result = run_backtest(
        [signal("THYAO", 2, "80"), signal("THYAO", 6, "30")],
        [
            price("THYAO", 2, "100"),
            price("THYAO", 5, "100"),
            price("THYAO", 6, "120"),
            price("THYAO", 7, "120"),
        ],
    )

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert result.trades[1].execution_date == date(2026, 1, 7)
    assert result.trades[1].realized_pnl is not None
    assert result.trades[1].realized_pnl > 0
    assert result.metrics.closed_trades == 1
    assert result.metrics.winning_trades == 1
    assert result.metrics.win_rate_pct == Decimal("100.0000")


def test_open_position_is_marked_to_market_without_synthetic_final_sale():
    result = run_backtest(
        [signal("THYAO", 2, "80")],
        [price("THYAO", 5, "100"), price("THYAO", 6, "125")],
    )

    assert [trade.side for trade in result.trades] == ["BUY"]
    assert result.metrics.closed_trades == 0
    assert result.metrics.win_rate_pct is None
    assert result.points[-1].position_count == 1
    assert result.metrics.final_equity > result.metrics.initial_cash


def test_fee_slippage_drawdown_and_risk_metrics_are_reported():
    result = run_backtest(
        [signal("THYAO", 2, "80")],
        [
            price("THYAO", 5, "100"),
            price("THYAO", 6, "80"),
            price("THYAO", 7, "120"),
        ],
    )

    assert result.metrics.total_fees > 0
    assert result.metrics.max_drawdown_pct > 0
    assert result.metrics.annualized_volatility_pct is not None
    assert result.metrics.sharpe_ratio is not None


def test_empty_dataset_returns_cash_only_result():
    config = BacktestConfig(initial_cash=Decimal(250000))
    result = run_backtest([], [], config=config)

    assert result.points == ()
    assert result.trades == ()
    assert result.metrics.final_equity == Decimal("250000.0000")
    assert result.metrics.total_return_pct == Decimal("0.0000")


def test_invalid_configuration_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="exit < entry"):
        BacktestConfig(entry_score=Decimal(30), exit_score=Decimal(40))


def test_stop_loss_sells_and_blocks_same_day_reentry_like_paper():
    config = BacktestConfig(stop_loss_pct=Decimal(15))
    result = run_backtest(
        # 6 Ocak skoru hala yuksek; zarar-kes gunu (7 Ocak) yeniden alim yapilmaz.
        [signal("THYAO", 2, "80"), signal("THYAO", 6, "90")],
        [price("THYAO", 2, "100"), price("THYAO", 5, "100"), price("THYAO", 6, "100"),
         price("THYAO", 7, "80"), price("THYAO", 8, "80")],
        config=config,
    )

    sides = [(trade.side, trade.execution_date.day) for trade in result.trades]
    assert sides == [("BUY", 5), ("SELL", 7)]
    assert result.trades[1].realized_pnl < 0


def test_daily_entry_cap_spreads_new_positions_over_days():
    tickers = ["AAAA", "BBBB", "CCCC", "DDDD", "EEEE"]
    signals = [signal(ticker, 2, "80") for ticker in tickers] + [
        signal(ticker, 5, "80") for ticker in tickers
    ]
    prices = [price(ticker, day, "100") for ticker in tickers for day in (2, 5, 6)]

    capped = run_backtest(signals, prices, config=BacktestConfig(max_new_entries_per_day=3))
    unlimited = run_backtest(signals, prices)

    buys_by_day = {}
    for trade in capped.trades:
        buys_by_day[trade.execution_date.day] = buys_by_day.get(trade.execution_date.day, 0) + 1
    assert buys_by_day == {5: 3, 6: 2}
    assert len([trade for trade in unlimited.trades if trade.execution_date.day == 5]) == 5
