"""Paper portfoy risk kurallari ve metrikleri (saf fonksiyonlar, DB'siz).

Tum esikler yuzde olarak verilir; 0 degeri kurali kapatir. Uygulama ayarlarinin
varsayilanlari (core/config.py) zarar-kes %15, sektor limiti %30, tek pozisyon
tavani %10 ve rebalance acik seklindedir; asagidaki RiskConfig varsayilanlari
ise kurallari kapali tutar (saf fonksiyon testleri icin). Canli emir yoktur.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal
from itertools import pairwise
from typing import Any

EXIT_REASONS = ("stop_loss", "take_profit", "trailing_stop", "signal", "rebalance")
TRADING_DAYS = 252
REBALANCE_TOLERANCE = Decimal("1.25")  # tavanin %25 ustune cikmadan trim yapilmaz


@dataclass(frozen=True)
class RiskConfig:
    stop_loss_pct: Decimal = Decimal(0)
    take_profit_pct: Decimal = Decimal(0)
    trailing_stop_pct: Decimal = Decimal(0)
    max_position_weight: Decimal = Decimal("0.10")
    max_sector_weight: Decimal = Decimal(0)  # 0 = sinirsiz
    rebalance_enabled: bool = False

    @classmethod
    def from_settings(cls, settings: Any) -> RiskConfig:
        def pct(name: str, default: str) -> Decimal:
            return Decimal(str(getattr(settings, name, default)))

        return cls(
            stop_loss_pct=pct("paper_stop_loss_pct", "0"),
            take_profit_pct=pct("paper_take_profit_pct", "0"),
            trailing_stop_pct=pct("paper_trailing_stop_pct", "0"),
            max_position_weight=pct("paper_max_position_weight_pct", "10") / 100,
            max_sector_weight=pct("paper_max_sector_weight_pct", "0") / 100,
            rebalance_enabled=bool(getattr(settings, "paper_rebalance_enabled", False)),
        )


@dataclass(frozen=True)
class PositionState:
    ticker: str
    quantity: Decimal
    average_cost: Decimal
    last_price: Decimal
    high_water_price: Decimal | None = None


@dataclass(frozen=True)
class RiskAction:
    ticker: str
    reason_code: str
    quantity: Decimal  # satilacak adet
    detail: str


def update_high_water(previous: Decimal | None, price: Decimal, average_cost: Decimal) -> Decimal:
    """Trailing stop icin pozisyon boyunca goruleni en yuksek fiyat (maliyetin altina inmez)."""
    return max(previous or average_cost, average_cost, price)


def evaluate_exit(position: PositionState, cfg: RiskConfig) -> tuple[str, str] | None:
    """Stop-loss, trailing stop, take-profit sirasiyla kontrol eder; (kod, aciklama) doner."""
    cost, price = position.average_cost, position.last_price
    if cost <= 0 or price <= 0:
        return None
    change_pct = (price / cost - 1) * 100
    if cfg.stop_loss_pct > 0 and change_pct <= -cfg.stop_loss_pct:
        return "stop_loss", f"Zarar-kes: {change_pct:.2f}% <= -{cfg.stop_loss_pct}%"
    peak = update_high_water(position.high_water_price, price, cost)
    if cfg.trailing_stop_pct > 0 and peak > cost:
        drop_pct = (1 - price / peak) * 100
        if drop_pct >= cfg.trailing_stop_pct:
            return (
                "trailing_stop",
                f"Trailing stop: zirveden -{drop_pct:.2f}% >= {cfg.trailing_stop_pct}%",
            )
    if cfg.take_profit_pct > 0 and change_pct >= cfg.take_profit_pct:
        return "take_profit", f"Kâr-al: {change_pct:.2f}% >= {cfg.take_profit_pct}%"
    return None


def trim_quantity(position: PositionState, *, equity: Decimal, cfg: RiskConfig) -> Decimal:
    """Agirlik tavanin tolerans ustundeyse tavana inmek icin satilacak tam adet."""
    if not cfg.rebalance_enabled or equity <= 0 or cfg.max_position_weight <= 0:
        return Decimal(0)
    if position.last_price <= 0 or position.quantity <= 1:
        return Decimal(0)
    value = position.quantity * position.last_price
    cap_value = equity * cfg.max_position_weight
    if value <= cap_value * REBALANCE_TOLERANCE:
        return Decimal(0)
    excess = ((value - cap_value) / position.last_price).to_integral_value(rounding=ROUND_FLOOR)
    return min(excess, position.quantity - 1)


def plan_position_actions(
    positions: Iterable[PositionState],
    *,
    scores: Mapping[str, Decimal],
    exit_score: Decimal,
    equity: Decimal,
    cfg: RiskConfig,
    skip_tickers: Iterable[str] = (),
) -> list[RiskAction]:
    """Gun sonu cikis/rebalance kararlari. `skip_tickers` bugun zaten satilmis hisselerdir;
    ayni gun ikinci kosu bu sayede sifir aksiyon uretir."""
    skip = set(skip_tickers)
    actions: list[RiskAction] = []
    for position in sorted(positions, key=lambda row: row.ticker):
        if position.ticker in skip:
            continue
        risk_exit = evaluate_exit(position, cfg)
        if risk_exit is not None:
            actions.append(
                RiskAction(position.ticker, risk_exit[0], position.quantity, risk_exit[1])
            )
            continue
        score = scores.get(position.ticker)
        if score is not None and score < exit_score:
            actions.append(
                RiskAction(
                    position.ticker,
                    "signal",
                    position.quantity,
                    f"Bileşik skor {float(score):.1f} < {exit_score}",
                )
            )
            continue
        trim = trim_quantity(position, equity=equity, cfg=cfg)
        if trim > 0:
            actions.append(
                RiskAction(
                    position.ticker,
                    "rebalance",
                    trim,
                    f"Rebalance: ağırlık %{cfg.max_position_weight * 100:.0f} tavanının üstünde",
                )
            )
    return actions


def entry_budget(
    *,
    ticker_sector: str,
    equity: Decimal,
    sector_values: Mapping[str, Decimal],
    cfg: RiskConfig,
) -> Decimal:
    """Yeni alim butcesi: tek pozisyon tavani ve (varsa) sektor tavaninin kalan payi."""
    budget = equity * cfg.max_position_weight
    if cfg.max_sector_weight > 0:
        headroom = equity * cfg.max_sector_weight - sector_values.get(ticker_sector, Decimal(0))
        budget = min(budget, headroom)
    return max(budget, Decimal(0))


# --- Metrikler -------------------------------------------------------------


def max_drawdown_pct(equities: list[float]) -> float:
    """Zirveden en buyuk dusus (pozitif yuzde)."""
    peak, worst = 0.0, 0.0
    for value in equities:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak * 100)
    return round(worst, 4)


def volatility_pct(equities: list[float]) -> float | None:
    """Gunluk getiri standart sapmasi, yillik (252 gun) yuzde. <3 nokta icin None."""
    returns = [b / a - 1 for a, b in pairwise(equities) if a > 0]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return round(math.sqrt(variance) * math.sqrt(TRADING_DAYS) * 100, 4)


def sector_allocation(
    values: Mapping[str, float], sector_of: Callable[[str], str], total: float
) -> list[dict[str, Any]]:
    """Hisse piyasa degerlerini sektore toplar; agirliklar toplam portfoy degerine gore."""
    totals: dict[str, float] = {}
    for ticker, value in values.items():
        sector = sector_of(ticker)
        totals[sector] = totals.get(sector, 0.0) + value
    rows = [
        {
            "sector": sector,
            "value": round(value, 4),
            "weight_pct": round(value / total * 100, 2) if total > 0 else 0.0,
        }
        for sector, value in totals.items()
    ]
    return sorted(rows, key=lambda row: (-row["value"], row["sector"]))


def compute_risk_metrics(
    *,
    equity_series: list[tuple[date, float]],
    position_values: Mapping[str, float],
    cash: float,
    sector_of: Callable[[str], str],
) -> dict[str, Any]:
    ordered = sorted(equity_series, key=lambda row: row[0])
    equities = [value for _, value in ordered]
    total = cash + sum(position_values.values())
    top_ticker = max(position_values, key=lambda key: position_values[key], default=None)
    return {
        "observations": len(equities),
        "max_drawdown_pct": max_drawdown_pct(equities),
        "volatility_pct": volatility_pct(equities),
        "top_position_ticker": top_ticker,
        "top_position_weight_pct": (
            round(position_values[top_ticker] / total * 100, 2) if top_ticker and total > 0 else 0.0
        ),
        "cash_weight_pct": round(cash / total * 100, 2) if total > 0 else 100.0,
        "sector_allocation": sector_allocation(position_values, sector_of, total),
    }
