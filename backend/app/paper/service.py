"""Bilesik sinyalleri EOD fiyatlarla kagit ustu portfoye uygular.

Bu modul araci kuruma baglanmaz ve canli emir gonderemez. Long-only, kaldiracsiz
ve tam adetli islemlerle risk sinirli bir degerlendirme ortami saglar.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dynamic_settings import resolve_settings
from app.core.sectors import resolve_sector
from app.models import (
    CompositeSignalSnapshot,
    IndexDaily,
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
from app.signals.service import MODEL_VERSION as SIGNAL_MODEL_VERSION

# v3: islemler yalniz islem gunlerinde ve sinyal gununden SONRAKI kapanista
# yapilir (backtest ile ayni kural). v2 ayni gunun kapanisinda, kapanistan sonra
# gelen haberlerle hesaplanmis skorla ve hafta sonlari da islem yapiyordu.
# v4: tavanda kapanan hisse alinmaz, tabanda kapanan satilmaz (BIST'te o
# kapanistan islem gerceklesmez); dusuk hacimli hisseye yeni pozisyon acilmaz.
STRATEGY_VERSION = "paper-v4"
DEFAULT_PORTFOLIO_NAME = "Ana Paper Portföy"
DEFAULT_INITIAL_CASH = Decimal(1000000)
ENTRY_SCORE = Decimal(75)
EXIT_SCORE = Decimal(40)
MIN_CONFIDENCE = Decimal("0.25")
MAX_POSITIONS = 10
# Tek bir haber/kanit ayni gun portfoyun buyuk kismini doldurmasin; bos slotlar
# gunler icine yayilir.
MAX_NEW_ENTRIES_PER_DAY = 3
MAX_POSITION_WEIGHT = Decimal("0.10")
FEE_RATE = Decimal("0.001")
SLIPPAGE_RATE = Decimal("0.0005")
MIN_TRADE_VALUE = Decimal(1000)
BENCHMARK_INDEX = "XU100"
# Kacirilan islem gunleri (worker kesintisi, gec gelen fiyat) sirayla telafi edilir.
MAX_CATCH_UP_DAYS = 5
# Pozisyon degerlemesinde (islem degil) kabul edilen en eski fiyat.
MAX_MARK_STALE_DAYS = 7
# Gunluk degisim bu esige ulasirsa hisse tavan/tabanda sayilir (BIST limiti %10).
PRICE_LIMIT_PCT = Decimal("9.5")
# Yeni pozisyon icin son 20 islem gununun ortalama TL hacmi alt siniri.
MIN_AVG_VOLUME = Decimal(20_000_000)
VOLUME_WINDOW = 20


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


def entry_slots(*, open_count: int, bought_today: int) -> int:
    """Yeni pozisyon kotasi: gunluk sinir o gun daha once yapilan alimlari da sayar."""
    return max(0, min(MAX_NEW_ENTRIES_PER_DAY - bought_today, MAX_POSITIONS - open_count))


def pending_execution_days(
    trading_days: list[date], last_processed: date | None, *, limit: int = MAX_CATCH_UP_DAYS
) -> list[date]:
    """Henuz islenmemis islem gunleri (eskiden yeniye).

    Portfoy hic islenmemisse yalniz son islem gunu doner; gecmis gunler toplu
    olarak yeniden oynatilmaz. Islenecek gun yoksa (hafta sonu, ayni gun ikinci
    kosu) bos liste doner ve kosu hicbir sey yazmaz.
    """
    ordered = sorted(set(trading_days))
    if not ordered:
        return []
    if last_processed is None:
        return ordered[-1:]
    return [day for day in ordered if day > last_processed][-limit:]


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
    # Cagiran yalniz MAX_MARK_STALE_DAYS icindeki fiyatlari kullanir; ~600 hissenin
    # tum fiyat gecmisi pencere fonksiyonuyla siralanmaz.
    ranked = (
        select(
            PriceDaily.ticker.label("ticker"),
            PriceDaily.date.label("date"),
            PriceDaily.close.label("close"),
            func.row_number()
            .over(partition_by=PriceDaily.ticker, order_by=PriceDaily.date.desc())
            .label("rank"),
        )
        .where(
            PriceDaily.ticker.in_(tickers),
            PriceDaily.date <= as_of_date,
            PriceDaily.date >= as_of_date - timedelta(days=MAX_MARK_STALE_DAYS),
        )
        .subquery()
    )
    rows = (await session.execute(select(ranked).where(ranked.c.rank == 1))).all()
    return {row.ticker: (row.date, _decimal(row.close)) for row in rows}


async def _execution_context(
    session: AsyncSession, tickers: set[str], execution_date: date
) -> dict[str, tuple[Decimal | None, Decimal]]:
    """Hisse -> (onceki kapanis, son 20 islem gununun ortalama TL hacmi); ikisi de
    islem gununden ONCEKI verilerle (karar aninda bilinen)."""
    if not tickers:
        return {}
    ranked = (
        select(
            PriceDaily.ticker.label("ticker"),
            PriceDaily.close.label("close"),
            PriceDaily.volume_try.label("volume_try"),
            func.row_number()
            .over(partition_by=PriceDaily.ticker, order_by=PriceDaily.date.desc())
            .label("rank"),
        )
        .where(
            PriceDaily.ticker.in_(tickers),
            PriceDaily.date < execution_date,
            PriceDaily.date >= execution_date - timedelta(days=45),
        )
        .subquery()
    )
    rows = (await session.execute(select(ranked).where(ranked.c.rank <= VOLUME_WINDOW))).all()
    previous: dict[str, Decimal] = {}
    volumes: dict[str, list[Decimal]] = {}
    for row in rows:
        if row.rank == 1:
            previous[row.ticker] = _decimal(row.close)
        volumes.setdefault(row.ticker, []).append(_decimal(row.volume_try or 0))
    return {
        ticker: (previous.get(ticker), sum(values, Decimal(0)) / len(values))
        for ticker, values in volumes.items()
    }


def day_change_pct(close: Decimal, previous: Decimal | None) -> Decimal:
    if previous is None or previous <= 0:
        return Decimal(0)
    return (close / previous - 1) * 100


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
    """Islenmemis her islem gunu icin bir onceki sinyalle o gunun kapanisinda islem yapar.

    `as_of_date` verilirse yalniz o gun islenir (elle yeniden oynatma).
    """
    has_signals = await session.scalar(
        select(func.max(CompositeSignalSnapshot.as_of_date)).where(
            CompositeSignalSnapshot.model_version == SIGNAL_MODEL_VERSION
        )
    )
    if has_signals is None:
        return {"portfolio": portfolio_name, "status": "no_signals", "trades": 0}

    portfolio = await _get_or_create_portfolio(session, portfolio_name, initial_cash)
    risk = risk_config or await load_risk_config()
    if as_of_date is not None:
        days = [as_of_date]
    else:
        today = datetime.now(ZoneInfo(get_settings().tz)).date()
        last_processed = await session.scalar(
            select(func.max(PaperPortfolioSnapshot.snapshot_date)).where(
                PaperPortfolioSnapshot.portfolio_id == portfolio.id
            )
        )
        trading_days = list(
            (
                await session.scalars(
                    select(IndexDaily.date).where(
                        IndexDaily.index_code == BENCHMARK_INDEX,
                        IndexDaily.date <= today,
                        IndexDaily.date >= today - timedelta(days=30),
                    )
                )
            ).all()
        )
        days = pending_execution_days(trading_days, last_processed)

    results = [await _run_day(session, portfolio, day, risk) for day in days]
    if not results:
        await session.commit()
        return {
            "portfolio_id": portfolio.id,
            "portfolio": portfolio.name,
            "strategy_version": STRATEGY_VERSION,
            "status": "up_to_date",
            "days": [],
            "trades": 0,
        }
    latest = results[-1]
    return {
        **latest,
        "days": [item["as_of_date"] for item in results],
        "buys": sum(item["buys"] for item in results),
        "sells": sum(item["sells"] for item in results),
        "trades": sum(item["trades"] for item in results),
    }


async def _run_day(
    session: AsyncSession,
    portfolio: PaperPortfolio,
    execution_date: date,
    risk: RiskConfig,
) -> dict[str, Any]:
    # Yurutme gunu skoru kapanistan sonra gelen haberleri de icerir; bu yuzden
    # bir onceki sinyal gununun (hafta sonu dahil) son skoru kullanilir.
    signal_date = await session.scalar(
        select(func.max(CompositeSignalSnapshot.as_of_date)).where(
            CompositeSignalSnapshot.model_version == SIGNAL_MODEL_VERSION,
            CompositeSignalSnapshot.as_of_date < execution_date,
        )
    )
    # Strateji yalniz bu kolonlari okur; bilesen/kanit JSONB'leri yuklenmez.
    signals = (
        list(
            (
                await session.execute(
                    select(
                        CompositeSignalSnapshot.id,
                        CompositeSignalSnapshot.ticker,
                        CompositeSignalSnapshot.composite_score,
                        CompositeSignalSnapshot.confidence,
                        CompositeSignalSnapshot.coverage_count,
                    )
                    .where(
                        CompositeSignalSnapshot.as_of_date == signal_date,
                        CompositeSignalSnapshot.model_version == SIGNAL_MODEL_VERSION,
                    )
                    .order_by(
                        CompositeSignalSnapshot.composite_score.desc(),
                        CompositeSignalSnapshot.ticker,
                    )
                )
            ).all()
        )
        if signal_date is not None
        else []
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
    prices = await _latest_prices(session, price_tickers, execution_date)
    mark_prices = {
        ticker: price
        for ticker, (price_date, price) in prices.items()
        if 0 <= (execution_date - price_date).days <= MAX_MARK_STALE_DAYS
    }
    # Islem yalniz o gunun kapanisiyla yapilir; islem gormeyen hisse eski fiyattan
    # alinip satilmaz (yalniz degerlenir).
    trade_prices = {
        ticker: price
        for ticker, (price_date, price) in prices.items()
        if price_date == execution_date
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
    context = await _execution_context(session, set(trade_prices), execution_date)

    def sector_of(ticker: str) -> str:
        return resolve_sector(ticker, names.get(ticker))

    def change(ticker: str) -> Decimal:
        return day_change_pct(trade_prices[ticker], context.get(ticker, (None, Decimal(0)))[0])

    # Ayni gunun onceki kosularinda (strateji surumunden bagimsiz) yapilan islemler.
    traded_today = (
        await session.execute(
            select(PaperTrade.ticker, PaperTrade.side).where(
                PaperTrade.portfolio_id == portfolio.id,
                PaperTrade.trade_date == execution_date,
            )
        )
    ).all()
    sold_today = {row.ticker for row in traded_today if row.side == "SELL"}
    bought_today = {row.ticker for row in traded_today if row.side == "BUY"}

    cash = _decimal(portfolio.cash_balance)
    realized_total = _decimal(portfolio.realized_pnl)
    fee_total = _decimal(portfolio.total_fees)
    trades: list[PaperTrade] = []
    sold: set[str] = set()  # bu kosuda kismen veya tamamen satilanlar
    closed: set[str] = set()  # tamamen satilip silinenler

    # Once mevcut pozisyonlari son EOD fiyatina tasir (trailing icin zirveyi gunceller).
    states: list[PositionState] = []
    for ticker, position in sorted(position_by_ticker.items()):
        close = mark_prices.get(ticker)
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
        if ticker in trade_prices:
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
            skip_tickers=sold_today | bought_today,
        )
        if portfolio.status == "ACTIVE"
        else []
    )
    for action in actions:
        ticker = action.ticker
        if change(ticker) <= -PRICE_LIMIT_PCT:
            # Tabanda kapandi: satis emri gerceklesmez; ertesi islem gunu yeniden degerlendirilir.
            continue
        position = position_by_ticker[ticker]
        close = trade_prices[ticker]
        average_cost = _decimal(position.average_cost)
        signal = signal_by_ticker.get(ticker)
        key = execution_key(portfolio.id, ticker, execution_date, "SELL", STRATEGY_VERSION)
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
                trade_date=execution_date,
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
        sold.add(ticker)
        remaining = _decimal(position.quantity) - order.quantity
        if remaining <= 0:
            await session.delete(position)
            closed.add(ticker)
        else:
            position.quantity = remaining
            position.market_value = _money(remaining * close)
            position.unrealized_pnl = _money((close - average_cost) * remaining)

    open_positions = {
        ticker: position for ticker, position in position_by_ticker.items() if ticker not in closed
    }
    positions_value = sum(
        (_decimal(position.market_value) for position in open_positions.values()), Decimal(0)
    )
    equity_before_entries = cash + positions_value

    # Guclu sinyaller arasindan bos slot kadar esit-riskli yeni pozisyon acar. Ayni
    # gun satilan hisse (zarar-kes sonrasi skor hala yuksek olsa da) geri alinmaz;
    # aksi halde ayni flush'ta yeni pozisyonun INSERT'u eskinin DELETE'inden once
    # calisip (portfoy, hisse) tekligini bozar ve tum kosu geri alinir.
    if portfolio.status == "ACTIVE":
        entries = select_entry_signals(
            [
                row
                for row in signals
                if row.ticker in trade_prices
                and change(row.ticker) < PRICE_LIMIT_PCT
                and context.get(row.ticker, (None, Decimal(0)))[1] >= MIN_AVG_VOLUME
            ],
            held_tickers=set(open_positions) | sold | sold_today | bought_today,
            slots=entry_slots(open_count=len(open_positions), bought_today=len(bought_today)),
        )
        sector_values: dict[str, Decimal] = {}
        for ticker, position in open_positions.items():
            sector = sector_of(ticker)
            sector_values[sector] = sector_values.get(sector, Decimal(0)) + _decimal(
                position.market_value
            )
        for signal in entries:
            close = trade_prices[signal.ticker]
            key = execution_key(
                portfolio.id, signal.ticker, execution_date, "BUY", STRATEGY_VERSION
            )
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
                    trade_date=execution_date,
                    side="BUY",
                    quantity=order.quantity,
                    price=order.price,
                    gross_amount=order.gross_amount,
                    fee_amount=order.fee_amount,
                    realized_pnl=None,
                    reason=(
                        f"Bileşik skor {float(signal.composite_score):.1f} ≥ {ENTRY_SCORE}; "
                        f"güven %{float(signal.confidence) * 100:.0f}; "
                        f"sinyal {signal_date:%d.%m.%Y}"
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
        "snapshot_date": execution_date,
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
        "as_of_date": execution_date.isoformat(),
        "signal_date": signal_date.isoformat() if signal_date else None,
        "signals": len(signals),
        "buys": sum(trade.side == "BUY" for trade in trades),
        "sells": sum(trade.side == "SELL" for trade in trades),
        "trades": len(trades),
        "positions": len(open_positions),
        "cash_balance": float(_money(cash)),
        "total_equity": float(_money(equity)),
    }
