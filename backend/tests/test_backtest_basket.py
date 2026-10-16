"""Siralama sepeti stratejisi ve agirlik simulasyonu testleri."""

from datetime import date
from decimal import Decimal

import pytest

from app.backtest import BacktestConfig, BacktestPrice, BacktestSignal, run_backtest
from app.backtest.engine import select_basket
from app.signals.service import (
    COMPONENT_WEIGHTS,
    ComponentResult,
    build_composite_signal,
    recombine_score,
)


def signal(ticker: str, day: int, score: str, *, confidence: str = "0.80") -> BacktestSignal:
    return BacktestSignal(ticker, date(2026, 1, day), Decimal(score), Decimal(confidence), 4)


def price(ticker: str, day: int, close: str, volume: str = "1000000000") -> BacktestPrice:
    return BacktestPrice(ticker, date(2026, 1, day), Decimal(close), Decimal(volume))


def basket(**overrides) -> BacktestConfig:
    params = {"strategy": "basket", "basket_size": 2, "basket_keep": 3, "rebalance_days": 2}
    params.update(overrides)
    return BacktestConfig(**params)


def test_select_basket_keeps_holdings_within_buffer_and_fills_by_rank():
    ranked = ["A", "B", "C", "D", "E"]
    assert select_basket(ranked, held=set(), size=2, keep=4) == ["A", "B"]
    # D hala ilk 4 icinde: korunur, bos yer en iyi siradan (A) doldurulur.
    assert select_basket(ranked, held={"D"}, size=2, keep=4) == ["D", "A"]
    # E tamponun disinda: birakilir.
    assert select_basket(ranked, held={"E"}, size=2, keep=4) == ["A", "B"]
    assert select_basket([], held={"A"}, size=2, keep=4) == []


def test_basket_buys_top_ranked_with_equal_weight_and_rebalances_on_schedule():
    signals = [
        signal("AAA", 1, "80"),
        signal("BBB", 1, "70"),
        signal("CCC", 1, "60"),
        # 3. gunun skorlari: CCC zirveye cikar, BBB tamponun (ilk 3) disina duser.
        signal("CCC", 3, "90"),
        signal("AAA", 3, "85"),
        signal("DDD", 3, "75"),
        signal("BBB", 3, "10"),
    ]
    prices = [price(t, d, "100") for t in ("AAA", "BBB", "CCC", "DDD") for d in (2, 3, 4)]
    result = run_backtest(signals, prices, config=basket(), start_date=date(2026, 1, 2))

    first_day = [t for t in result.trades if t.execution_date == date(2026, 1, 2)]
    assert sorted((t.ticker, t.side) for t in first_day) == [("AAA", "BUY"), ("BBB", "BUY")]
    # Esit agirlik: her biri sermayenin yarisina yakin.
    for trade in first_day:
        assert Decimal(480_000) < trade.gross_amount <= Decimal(500_000)
    # 3. gun dengeleme degil (her 2 islem gunu): islem yok.
    assert not [t for t in result.trades if t.execution_date == date(2026, 1, 3)]
    # 4. gun dengeleme: BBB satilir, CCC alinir; AAA tamponda oldugu icin tutulur.
    fourth = sorted(
        (t.ticker, t.side) for t in result.trades if t.execution_date == date(2026, 1, 4)
    )
    assert fourth == [("BBB", "SELL"), ("CCC", "BUY")]
    assert result.points[-1].position_count == 2


def test_basket_uses_only_scores_known_before_execution_day():
    # 2. gunun skoru 2. gunde islenemez; yalniz 1. gunun skoru kullanilir.
    signals = [signal("AAA", 1, "60"), signal("BBB", 2, "99")]
    prices = [price(t, d, "100") for t in ("AAA", "BBB") for d in (1, 2)]
    result = run_backtest(
        signals, prices, config=basket(basket_size=1), start_date=date(2026, 1, 2)
    )
    assert [(t.ticker, t.side) for t in result.trades] == [("AAA", "BUY")]


def test_basket_respects_liquidity_limit_up_and_retries_blocked_sell():
    signals = [
        signal("ILLQ", 1, "95"),
        signal("UP", 1, "90"),
        signal("OK", 1, "80"),
        signal("OK", 3, "10"),
        signal("NEW", 3, "85"),
        signal("UP", 3, "88"),
    ]
    prices = [
        price("ILLQ", 1, "100", volume="1000"),
        price("ILLQ", 2, "100", volume="1000"),
        price("UP", 1, "100"),
        price("UP", 2, "110"),  # tavan: 2. gun alinamaz
        price("UP", 3, "111"),  # ertesi gun (dengeleme beklenmeden) alinir
        price("OK", 1, "100"),
        price("OK", 2, "100"),
        price("OK", 3, "100"),
        price("OK", 4, "90"),  # tabanda: satis ertelenir
        price("OK", 5, "91"),
        price("NEW", 3, "100"),
        price("NEW", 4, "100"),
        price("NEW", 5, "100"),
        price("UP", 4, "111"),
        price("UP", 5, "111"),
    ]
    # Tutma tamponu 2: 4. gun OK hedeften cikar (tabanda oldugu icin satis 5. gune kayar).
    config = basket(
        basket_keep=2, min_avg_volume=Decimal(1_000_000), price_limit_pct=Decimal("9.5")
    )
    result = run_backtest(signals, prices, config=config, start_date=date(2026, 1, 2))
    by_day = {}
    for trade in result.trades:
        by_day.setdefault(trade.execution_date.day, []).append((trade.ticker, trade.side))
    assert all(("ILLQ", "BUY") not in trades for trades in by_day.values())
    assert by_day[2] == [("OK", "BUY")]
    assert by_day[3] == [("UP", "BUY")]
    assert ("OK", "SELL") not in by_day.get(4, [])
    assert ("OK", "SELL") in by_day[5]


def test_basket_regime_filter_moves_to_cash():
    signals = [signal("AAA", 1, "80"), signal("AAA", 3, "80")]
    prices = [price("AAA", d, "100") for d in (2, 3, 4)]
    # Her dengeleme gununden onceki kapanis 2 gunluk ortalamanin altinda.
    falling = [(date(2025, 12, 31), Decimal(1000))] + [
        (date(2026, 1, d), Decimal(900 - d * 10)) for d in range(1, 5)
    ]
    result = run_backtest(
        signals,
        prices,
        config=basket(basket_size=1, regime_ma_days=2),
        benchmark=falling,
        start_date=date(2026, 1, 2),
    )
    assert result.trades == ()


def test_basket_config_validation():
    with pytest.raises(ValueError):
        BacktestConfig(strategy="momentum")
    with pytest.raises(ValueError):
        BacktestConfig(strategy="basket", basket_size=5, basket_keep=4)
    with pytest.raises(ValueError):
        BacktestConfig(strategy="basket", rebalance_days=0)


def test_default_exit_score_is_55():
    assert BacktestConfig().exit_score == Decimal(55)


def _components(**scores: tuple[str, str]) -> dict[str, ComponentResult]:
    return {
        name: ComponentResult(Decimal(score), Decimal(confidence), {})
        for name, (score, confidence) in scores.items()
    }


@pytest.mark.parametrize(
    "components",
    [
        _components(llm=("80", "0.9"), fundamental=("60", "0.7"), analyst=("30", "0.5")),
        _components(fundamental=("70", "0.2"), momentum=("40", "0.4")),
        _components(
            llm=("55", "0.6"), fundamental=("65", "1"), analyst=("90", "0.8"), momentum=("20", "1")
        ),
    ],
)
def test_recombine_with_original_weights_reproduces_composite(components):
    built = build_composite_signal("THYAO", components, as_of_date=date(2026, 1, 2))
    recombined = recombine_score(
        built["component_scores"],
        COMPONENT_WEIGHTS,
        confidence=built["confidence"],
        component_confidences=built["evidence"]["confidences"],
    )
    assert abs(recombined - built["composite_score"]) <= Decimal("0.01")


def test_recombine_drops_zero_weight_components_and_falls_back_to_stored_confidence():
    scores = {"llm": 90.0, "analyst": 10.0}
    weights = {**COMPONENT_WEIGHTS, "analyst": Decimal(0)}
    # Bilesen guveni yok (eski satir): kayitli toplam guven (0.60 -> daraltma yok).
    assert recombine_score(scores, weights, confidence=Decimal("0.60")) == Decimal("90.00")
    # Guven yarim: skor 50'ye dogru yari yari cekilir.
    assert recombine_score(scores, weights, confidence=Decimal("0.30")) == Decimal("70.00")
    assert recombine_score({"analyst": 10.0}, weights, confidence=Decimal(1)) is None
