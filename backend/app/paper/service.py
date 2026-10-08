"""Bilesik sinyalleri EOD fiyatlarla kagit ustu portfoye uygular.

Bu modul araci kuruma baglanmaz ve canli emir gonderemez. Long-only, kaldiracsiz
ve tam adetli islemlerle risk sinirli bir degerlendirme ortami saglar.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dynamic_settings import resolve_settings
from app.core.sectors import resolve_sector
from app.models import (
    CompositeSignalSnapshot,
    Instrument,
    PaperPortfolio,
    PaperPortfolioSnapshot,
    PaperPosition,
    PaperTrade,
    PriceDaily,
)
from app.paper.risk import (
    PositionState,
    RiskConfig,
    entry_budget,
    plan_position_actions,
    update_high_water,
)

STRATEGY_VERSION = "paper-v1"
SIGNAL_MODEL_VERSION = "v1"
DEFAULT_PORTFOLIO_NAME = "Ana Paper Portföy"
DEFAULT_INITIAL_CASH = Decimal(1000000)
ENTRY_SCORE = Decimal(75)
EXIT_SCORE = Decimal(40)
MIN_CONFIDENCE = Decimal("0.25")
MAX_POSITIONS = 10
MAX_POSITION_WEIGHT = Decimal("0.10")
FEE_RATE = Decimal("0.001")
SLIPPAGE_RATE = Decimal("0.0005")
MIN_TRADE_VALUE = Decimal(1000)


@dataclass(frozen=True)
class OrderPlan:
    ticker: str
    side: str
    quantity: Decimal
    price: Decimal
    gross_amount: Decimal
    fee_amount: Decimal


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def execution_key(
    portfolio_id: int, ticker: str, trade_date: date, side: str, strategy_version: str
) -> str:
    payload = f"{portfolio_id}|{ticker}|{trade_date.isoformat()}|{side}|{strategy_version}"
    return hashlib.sha256(payload.encode()).hexdigest()


def plan_buy(
    ticker: str,
    *,
    close_price: Decimal,
    budget: Decimal,
    cash: Decimal,
) -> OrderPlan | None:
    if close_price <= 0 or budget <= 0 or cash <= 0:
        return None
    price = close_price * (Decimal(1) + SLIPPAGE_RATE)
    available = min(budget, cash)
    quantity = (available / (price * (Decimal(1) + FEE_RATE))).to_integral_value(
        rounding=ROUND_FLOOR
    )
    if quantity <= 0:
        return None
    gross = _money(quantity * price)
    fee = _money(gross * FEE_RATE)
    while quantity > 0 and gross + fee > cash:
        quantity -= 1
        gross = _money(quantity * price)
        fee = _money(gross * FEE_RATE)
    if quantity <= 0 or gross < MIN_TRADE_VALUE:
        return None
    return OrderPlan(ticker, "BUY", quantity, price, gross, fee)


def plan_sell(ticker: str, *, close_price: Decimal, quantity: Decimal) -> OrderPlan | None:
    if close_price <= 0 or quantity <= 0:
        return None
    price = close_price * (Decimal(1) - SLIPPAGE_RATE)
    gross = _money(quantity * price)
    fee = _money(gross * FEE_RATE)
    return OrderPlan(ticker, "SELL", quantity, price, gross, fee)


def select_entry_signals(signals: list[Any], *, held_tickers: set[str], slots: int) -> list[Any]:
    eligible = [
        row
        for row in signals
        if row.ticker not in held_tickers
        and _decimal(row.composite_score) >= ENTRY_SCORE
        and _decimal(row.confidence) >= MIN_CONFIDENCE
        and row.coverage_count >= 2
    ]
    return sorted(eligible, key=lambda row: (-_decimal(row.composite_score), row.ticker))[:slots]


async def _get_or_create_portfolio(
    session: AsyncSession, name: str, initial_cash: Decimal
) -> PaperPortfolio:
    portfolio = await session.scalar(select(PaperPortfolio).where(PaperPortfolio.name == name))
    if portfolio is not None:
        return portfolio
    portfolio = PaperPortfolio(
        name=name,
        strategy_version=STRATEGY_VERSION,
        base_currency="TRY",
        status="ACTIVE",
        initial_cash=initial_cash,
        cash_balance=initial_cash,
        realized_pnl=Decimal(0),
        total_fees=Decimal(0),
    )
    session.add(portfolio)
    await session.flush()
    return portfolio


async def _latest_prices(
    session: AsyncSession, tickers: set[str], as_of_date: date
) -> dict[str, tuple[date, Decimal]]:
    if not tickers:
        return {}
    ranked = (
        select(
            PriceDaily.ticker.label("ticker"),
            PriceDaily.date.label("date"),
            PriceDaily.close.label("close"),
            func.row_number()
            .over(partition_by=PriceDaily.ticker, order_by=PriceDaily.date.desc())
            .label("rank"),
        )
        .where(PriceDaily.ticker.in_(tickers), PriceDaily.date <= as_of_date)
        .subquery()
    )
    rows = (await session.execute(select(ranked).where(ranked.c.rank == 1))).all()
    return {row.ticker: (row.date, _decimal(row.close)) for row in rows}


async def load_risk_config() -> RiskConfig:
    """Redis ayar override'lariyla birlesik risk kurallari; Redis yoksa .env varsayilanlari."""
    try:
        settings = await resolve_settings()
    except Exception:  # noqa: BLE001 - ayar okunamazsa varsayilanla devam et
        settings = get_settings()
    return RiskConfig.from_settings(settings)


async def run_paper_portfolio(
    session: AsyncSession,
    *,
    portfolio_name: str = DEFAULT_PORTFOLIO_NAME,
    initial_cash: Decimal = DEFAULT_INITIAL_CASH,
    as_of_date: date | None = None,
    risk_config: RiskConfig | None = None,
) -> dict[str, Any]:
    target_date = as_of_date or await session.scalar(
        select(func.max(CompositeSignalSnapshot.as_of_date)).where(
            CompositeSignalSnapshot.model_version == SIGNAL_MODEL_VERSION
        )
    )
    if target_date is None:
        return {"portfolio": portfolio_name, "status": "no_signals", "trades": 0}

    portfolio = await _get_or_create_portfolio(session, portfolio_name, initial_cash)
    risk = risk_config or await load_risk_config()
    signals = list(
        (
            await session.scalars(
                select(CompositeSignalSnapshot)
                .where(
                    CompositeSignalSnapshot.as_of_date == target_date,
                    CompositeSignalSnapshot.model_version == SIGNAL_MODEL_VERSION,
                )
                .order_by(
                    CompositeSignalSnapshot.composite_score.desc(),
                    CompositeSignalSnapshot.ticker,
                )
            )
        ).all()
    )
    signal_by_ticker = {row.ticker: row for row in signals}
    positions = list(
        (
            await session.scalars(
                select(PaperPosition).where(PaperPosition.portfolio_id == portfolio.id)
            )
        ).all()
    )
    position_by_ticker = {row.ticker: row for row in positions}
    price_tickers = set(signal_by_ticker) | set(position_by_ticker)
    prices = await _latest_prices(session, price_tickers, target_date)
    fresh_prices = {
        ticker: price
        for ticker, (price_date, price) in prices.items()
        if 0 <= (target_date - price_date).days <= 7
    }

    names = dict(
        (
            await session.execute(
                select(Instrument.ticker, Instrument.name).where(
                    Instrument.ticker.in_(price_tickers)
                )
            )
        ).all()
    )

    def sector_of(ticker: str) -> str:
        return resolve_sector(ticker, names.get(ticker))

    possible_keys = {
        execution_key(portfolio.id, ticker, target_date, side, STRATEGY_VERSION)
        for ticker in price_tickers
        for side in ("BUY", "SELL")
    }
    existing_keys = set(
        (
            await session.scalars(
                select(PaperTrade.execution_key).where(PaperTrade.execution_key.in_(possible_keys))
            )
        ).all()
    )

    cash = _decimal(portfolio.cash_balance)
    realized_total = _decimal(portfolio.realized_pnl)
    fee_total = _decimal(portfolio.total_fees)
    trades: list[PaperTrade] = []
    sold: set[str] = set()

    # Once mevcut pozisyonlari son EOD fiyatina tasir (trailing icin zirveyi gunceller).
    states: list[PositionState] = []
    for ticker, position in sorted(position_by_ticker.items()):
        close = fresh_prices.get(ticker)
        if close is None:
            continue
        quantity = _decimal(position.quantity)
        average_cost = _decimal(position.average_cost)
        position.last_price = close
        position.market_value = _money(quantity * close)
        position.unrealized_pnl = _money((close - average_cost) * quantity)
        position.high_water_price = update_high_water(
            None if position.high_water_price is None else _decimal(position.high_water_price),
            close,
            average_cost,
        )
        states.append(
            PositionState(ticker, quantity, average_cost, close, position.high_water_price)
        )
    marked_equity = cash + sum(
        (_decimal(position.market_value) for position in position_by_ticker.values()),
        Decimal(0),
    )

    # Cikislar: zarar-kes / trailing / kar-al / sinyal / rebalance (bugun satilmislar atlanir).
    actions = (
        plan_position_actions(
            states,
            scores={
                ticker: _decimal(row.composite_score) for ticker, row in signal_by_ticker.items()
            },
            exit_score=EXIT_SCORE,
            equity=marked_equity,
            cfg=risk,
            skip_tickers={
                ticker
                for ticker in position_by_ticker
                if execution_key(portfolio.id, ticker, target_date, "SELL", STRATEGY_VERSION)
                in existing_keys
            },
        )
        if portfolio.status == "ACTIVE"
        else []
    )
    for action in actions:
        ticker = action.ticker
        position = position_by_ticker[ticker]
        close = fresh_prices[ticker]
        average_cost = _decimal(position.average_cost)
        signal = signal_by_ticker.get(ticker)
        key = execution_key(portfolio.id, ticker, target_date, "SELL", STRATEGY_VERSION)
        order = plan_sell(ticker, close_price=close, quantity=action.quantity)
        if order is None:
            continue
        realized = _money(order.gross_amount - order.fee_amount - average_cost * order.quantity)
        cash += order.gross_amount - order.fee_amount
        realized_total += realized
        fee_total += order.fee_amount
        trades.append(
            PaperTrade(
                execution_key=key,
                portfolio_id=portfolio.id,
                ticker=ticker,
                signal_snapshot_id=signal.id if signal is not None else None,
                strategy_version=STRATEGY_VERSION,
                trade_date=target_date,
                side="SELL",
                quantity=order.quantity,
                price=order.price,
                gross_amount=order.gross_amount,
                fee_amount=order.fee_amount,
                realized_pnl=realized,
                reason=action.detail,
                exit_reason=action.reason_code,
            )
        )
        remaining = _decimal(position.quantity) - order.quantity
        if remaining <= 0:
            await session.delete(position)
            sold.add(ticker)
        else:
            position.quantity = remaining
            position.market_value = _money(remaining * close)
            position.unrealized_pnl = _money((close - average_cost) * remaining)

    open_positions = {
        ticker: position for ticker, position in position_by_ticker.items() if ticker not in sold
    }
    positions_value = sum(
        (_decimal(position.market_value) for position in open_positions.values()), Decimal(0)
    )
    equity_before_entries = cash + positions_value

    # Guclu sinyaller arasindan bos slot kadar esit-riskli yeni pozisyon acar.
    if portfolio.status == "ACTIVE":
        entries = select_entry_signals(
            signals,
            held_tickers=set(open_positions),
            slots=max(0, MAX_POSITIONS - len(open_positions)),
        )
        sector_values: dict[str, Decimal] = {}
        for ticker, position in open_positions.items():
            sector = sector_of(ticker)
            sector_values[sector] = sector_values.get(sector, Decimal(0)) + _decimal(
                position.market_value
            )
        for signal in entries:
            close = fresh_prices.get(signal.ticker)
            if close is None:
                continue
            key = execution_key(portfolio.id, signal.ticker, target_date, "BUY", STRATEGY_VERSION)
            if key in existing_keys:
                continue
            sector = sector_of(signal.ticker)
            target_budget = entry_budget(
                ticker_sector=sector,
                equity=equity_before_entries,
                sector_values=sector_values,
                cfg=risk,
            )
            order = plan_buy(signal.ticker, close_price=close, budget=target_budget, cash=cash)
            if order is None:
                continue
            sector_values[sector] = sector_values.get(sector, Decimal(0)) + _money(
                order.quantity * close
            )
            total_cost = order.gross_amount + order.fee_amount
            average_cost = total_cost / order.quantity
            position = PaperPosition(
                portfolio_id=portfolio.id,
                ticker=signal.ticker,
                quantity=order.quantity,
                average_cost=average_cost,
                last_price=close,
                high_water_price=max(close, average_cost),
                market_value=_money(order.quantity * close),
                unrealized_pnl=_money((close - average_cost) * order.quantity),
            )
            session.add(position)
            open_positions[signal.ticker] = position
            cash -= total_cost
            fee_total += order.fee_amount
            trades.append(
                PaperTrade(
                    execution_key=key,
                    portfolio_id=portfolio.id,
                    ticker=signal.ticker,
                    signal_snapshot_id=signal.id,
                    strategy_version=STRATEGY_VERSION,
                    trade_date=target_date,
                    side="BUY",
                    quantity=order.quantity,
                    price=order.price,
                    gross_amount=order.gross_amount,
                    fee_amount=order.fee_amount,
                    realized_pnl=None,
                    reason=(
                        f"Bilesik skor {signal.composite_score} >= {ENTRY_SCORE}; "
                        f"guven {signal.confidence}"
                    ),
                    exit_reason=None,
                )
            )

    if trades:
        session.add_all(trades)
    portfolio.cash_balance = _money(cash)
    portfolio.realized_pnl = _money(realized_total)
    portfolio.total_fees = _money(fee_total)
    portfolio.strategy_version = STRATEGY_VERSION
    await session.flush()

    positions_value = sum(
        (_decimal(position.market_value) for position in open_positions.values()), Decimal(0)
    )
    unrealized = sum(
        (_decimal(position.unrealized_pnl) for position in open_positions.values()), Decimal(0)
    )
    equity = cash + positions_value
    total_return = (equity / _decimal(portfolio.initial_cash) - 1) * 100
    weights = {
        ticker: float((_decimal(position.market_value) / equity * 100).quantize(Decimal("0.01")))
        for ticker, position in sorted(open_positions.items())
        if equity > 0
    }
    snapshot_fields = {
        "portfolio_id": portfolio.id,
        "snapshot_date": target_date,
        "cash_balance": _money(cash),
        "positions_value": _money(positions_value),
        "total_equity": _money(equity),
        "realized_pnl": _money(realized_total),
        "unrealized_pnl": _money(unrealized),
        "total_return_pct": total_return,
        "position_count": len(open_positions),
        "weights": weights,
    }
    stmt = pg_insert(PaperPortfolioSnapshot).values(**snapshot_fields)
    await session.execute(
        stmt.on_conflict_do_update(
            constraint="uq_paper_portfolio_snapshot_identity",
            set_={
                **{
                    key: getattr(stmt.excluded, key)
                    for key in snapshot_fields
                    if key not in {"portfolio_id", "snapshot_date"}
                },
                "computed_at": func.now(),
                "updated_at": func.now(),
            },
        )
    )
    await session.commit()
    return {
        "portfolio_id": portfolio.id,
        "portfolio": portfolio.name,
        "strategy_version": STRATEGY_VERSION,
        "as_of_date": target_date.isoformat(),
        "signals": len(signals),
        "buys": sum(trade.side == "BUY" for trade in trades),
        "sells": sum(trade.side == "SELL" for trade in trades),
        "trades": len(trades),
        "positions": len(open_positions),
        "cash_balance": float(_money(cash)),
        "total_equity": float(_money(equity)),
    }
