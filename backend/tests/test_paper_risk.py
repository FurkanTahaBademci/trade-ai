"""Paper risk yonetimi: saf fonksiyon testleri (DB'siz)."""

from datetime import date
from decimal import Decimal

from app.core.config import Settings
from app.main import app
from app.paper.risk import (
    PositionState,
    RiskConfig,
    compute_risk_metrics,
    entry_budget,
    evaluate_exit,
    max_drawdown_pct,
    plan_position_actions,
    trim_quantity,
    update_high_water,
    volatility_pct,
)

D = Decimal


def pos(ticker="AAAA", qty=100, cost=100, last=100, peak=None):
    return PositionState(ticker, D(qty), D(cost), D(last), None if peak is None else D(peak))


def test_defaults_keep_existing_behaviour():
    cfg = RiskConfig.from_settings(Settings())
    assert cfg.max_position_weight == D("0.10")
    assert cfg.stop_loss_pct == cfg.take_profit_pct == cfg.trailing_stop_pct == 0
    assert cfg.max_sector_weight == 0 and not cfg.rebalance_enabled
    # kurallar kapaliyken buyuk kayip/kazanc bile cikis uretmez
    assert evaluate_exit(pos(last=10), cfg) is None
    assert evaluate_exit(pos(last=1000), cfg) is None


def test_stop_loss_take_profit_and_trailing():
    cfg = RiskConfig(stop_loss_pct=D(10), take_profit_pct=D(20), trailing_stop_pct=D(8))
    assert evaluate_exit(pos(last=89), cfg)[0] == "stop_loss"
    assert evaluate_exit(pos(last=91), cfg) is None
    assert evaluate_exit(pos(last=121), cfg)[0] == "take_profit"
    # zirve 115 iken 105'e dusus: -8.7% -> trailing; kar-al esigine ulasilmamis
    assert evaluate_exit(pos(last=105, peak=115), cfg)[0] == "trailing_stop"
    assert evaluate_exit(pos(last=110, peak=115), cfg) is None


def test_trailing_requires_gain_and_peak_never_below_cost():
    cfg = RiskConfig(trailing_stop_pct=D(5))
    assert evaluate_exit(pos(last=90), cfg) is None  # zirve=maliyet, kar yok
    assert update_high_water(None, D(90), D(100)) == D(100)
    assert update_high_water(D(120), D(110), D(100)) == D(120)


def test_entry_budget_respects_position_and_sector_caps():
    cfg = RiskConfig(max_position_weight=D("0.10"), max_sector_weight=D("0.25"))
    equity = D(1_000_000)
    assert entry_budget(ticker_sector="Banka", equity=equity, sector_values={}, cfg=cfg) == D(
        100_000
    )
    assert entry_budget(
        ticker_sector="Banka", equity=equity, sector_values={"Banka": D(200_000)}, cfg=cfg
    ) == D(50_000)
    assert (
        entry_budget(
            ticker_sector="Banka", equity=equity, sector_values={"Banka": D(300_000)}, cfg=cfg
        )
        == 0
    )
    off = RiskConfig()
    assert entry_budget(
        ticker_sector="Banka", equity=equity, sector_values={"Banka": D(900_000)}, cfg=off
    ) == D(100_000)


def test_rebalance_trims_only_when_enabled_and_beyond_tolerance():
    equity = D(1_000_000)
    big = pos(qty=1000, cost=100, last=200)  # 200k = %20 > %12.5
    assert trim_quantity(big, equity=equity, cfg=RiskConfig()) == 0
    cfg = RiskConfig(rebalance_enabled=True)
    assert trim_quantity(big, equity=equity, cfg=cfg) == D(500)
    near = pos(qty=1000, cost=100, last=110)  # %11
    assert trim_quantity(near, equity=equity, cfg=cfg) == 0


def test_action_priority_and_reason_codes():
    cfg = RiskConfig(stop_loss_pct=D(10), rebalance_enabled=True)
    actions = plan_position_actions(
        [pos("AAAA", last=80), pos("BBBB", last=100), pos("CCCC", qty=1000, last=200)],
        scores={"AAAA": D(30), "BBBB": D(20)},
        exit_score=D(40),
        equity=D(1_000_000),
        cfg=cfg,
    )
    assert [(a.ticker, a.reason_code) for a in actions] == [
        ("AAAA", "stop_loss"),  # skor da dusuk ama stop onceliklidir
        ("BBBB", "signal"),
        ("CCCC", "rebalance"),
    ]


def test_second_run_same_day_produces_no_actions():
    cfg = RiskConfig(stop_loss_pct=D(10), take_profit_pct=D(50), rebalance_enabled=True)
    book = {
        "AAAA": pos("AAAA", last=80),
        "BBBB": pos("BBBB", last=100),
        "CCCC": pos("CCCC", qty=1000, last=200),
        "DDDD": pos("DDDD", last=100),
    }
    scores = {"BBBB": D(10), "DDDD": D(60)}
    sold_today: set[str] = set()

    def run() -> list:
        actions = plan_position_actions(
            list(book.values()),
            scores=scores,
            exit_score=D(40),
            equity=D(1_000_000),
            cfg=cfg,
            skip_tickers=sold_today,
        )
        for action in actions:  # motorun uyguladigi durum gecisi
            sold_today.add(action.ticker)
            held = book[action.ticker]
            if action.quantity >= held.quantity:
                del book[action.ticker]
            else:
                book[action.ticker] = pos(
                    held.ticker,
                    held.quantity - action.quantity,
                    held.average_cost,
                    held.last_price,
                )
        return actions

    assert len(run()) == 3
    assert run() == []


def test_metrics():
    assert max_drawdown_pct([100, 120, 90, 110]) == 25.0
    assert max_drawdown_pct([100, 110]) == 0
    assert max_drawdown_pct([]) == 0
    assert volatility_pct([100, 101]) is None
    assert volatility_pct([100, 100, 100]) == 0
    assert volatility_pct([100, 110, 99, 120]) > 0
    metrics = compute_risk_metrics(
        equity_series=[(date(2026, 1, 2), 100.0), (date(2026, 1, 1), 120.0)],
        position_values={"AAAA": 50.0, "BBBB": 30.0, "CCCC": 10.0},
        cash=10.0,
        sector_of=lambda t: "X" if t != "CCCC" else "Y",
    )
    assert metrics["max_drawdown_pct"] == 16.6667
    assert metrics["top_position_ticker"] == "AAAA"
    assert metrics["top_position_weight_pct"] == 50.0
    assert metrics["cash_weight_pct"] == 10.0
    assert metrics["sector_allocation"][0] == {"sector": "X", "value": 80.0, "weight_pct": 80.0}


def test_risk_route_registered():
    assert "/api/paper/portfolios/{portfolio_id}/risk" in set(app.openapi()["paths"])
