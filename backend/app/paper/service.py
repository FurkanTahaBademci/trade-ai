"""Bilesik sinyalleri ve manuel emirleri EOD fiyatlarla kagit ustu portfoylere uygular.

Bu modul araci kuruma baglanmaz ve canli emir gonderemez. Long-only, kaldiracsiz
ve tam adetli islemlerle risk sinirli bir degerlendirme ortami saglar.

Her islem gunu icin sinyaller, fiyatlar ve hacimler bir kez yuklenir (`DayContext`)
ve tum portfoylere ayni veriyle uygulanir. Portfoyler ayri transaction'larda
islenir; biri hata alirsa digerleri etkilenmez, hata portfoyun `last_error`
alanina yazilir.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dynamic_settings import resolve_settings
from app.core.sectors import resolve_sector
from app.models import (
    CompositeSignalSnapshot,
    IndexDaily,
    Instrument,
    PaperOrder,
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
from app.paper.strategy import DEFAULT_PARAMS, StrategyConfig, StrategyParams
from app.signals.service import MODEL_VERSION as SIGNAL_MODEL_VERSION

logger = structlog.get_logger(__name__)

# v3: islemler yalniz islem gunlerinde ve sinyal gununden SONRAKI kapanista
# yapilir (backtest ile ayni kural). v2 ayni gunun kapanisinda, kapanistan sonra
# gelen haberlerle hesaplanmis skorla ve hafta sonlari da islem yapiyordu.
# v4: tavanda kapanan hisse alinmaz, tabanda kapanan satilmaz (BIST'te o
# kapanistan islem gerceklesmez); dusuk hacimli hisseye yeni pozisyon acilmaz.
# v5: sinyal cikisi skor 40 yerine 55'in altinda. 6 aylik walk-forward'da
# egitimin en iyi bes kombinasyonunun hepsi 55 kullandi; 10 farkli baslangicta
# ortalama XU100'e gore fark -10,6 yerine -8,6 puan (6/10 baslangicta daha iyi).
STRATEGY_VERSION = "paper-v5"
MANUAL_VERSION = "manual-v1"
DEFAULT_PORTFOLIO_NAME = "Ana Paper Portföy"
DEFAULT_INITIAL_CASH = Decimal(1000000)
ENTRY_SCORE = DEFAULT_PARAMS.entry_score
EXIT_SCORE = DEFAULT_PARAMS.exit_score
MIN_CONFIDENCE = DEFAULT_PARAMS.min_confidence
MAX_POSITIONS = DEFAULT_PARAMS.max_positions
# Tek bir haber/kanit ayni gun portfoyun buyuk kismini doldurmasin; bos slotlar
# gunler icine yayilir.
MAX_NEW_ENTRIES_PER_DAY = DEFAULT_PARAMS.max_new_entries_per_day
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
# Manuel emir: surekli islem bu saatte biter; sonra verilen emir, kapanisi artik
# bilinen gune degil ertesi islem gunune yazilir.
ORDER_CUTOFF = time(18, 0)
# Bu kadar takvim gunu icinde gerceklesemeyen emir (islem gormeyen, tavan/tabanda
# kalan hisse) reddedilir.
ORDER_MAX_WAIT_DAYS = 7


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


def select_entry_signals(
    signals: list[Any],
    *,
    held_tickers: set[str],
    slots: int,
    params: StrategyParams = DEFAULT_PARAMS,
) -> list[Any]:
    eligible = [
        row
        for row in signals
        if row.ticker not in held_tickers
        and _decimal(row.composite_score) >= params.entry_score
        and _decimal(row.confidence) >= params.min_confidence
        and row.coverage_count >= params.min_coverage
    ]
    return sorted(eligible, key=lambda row: (-_decimal(row.composite_score), row.ticker))[:slots]


def entry_slots(
    *, open_count: int, bought_today: int, params: StrategyParams = DEFAULT_PARAMS
) -> int:
    """Yeni pozisyon kotasi: gunluk sinir o gun daha once yapilan alimlari da sayar."""
    return max(
        0,
        min(params.max_new_entries_per_day - bought_today, params.max_positions - open_count),
    )


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


# --- Manuel emirler (saf) -----------------------------------------------------


def next_weekday(day: date) -> date:
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def order_not_before(now: datetime, tz: str) -> date:
    """Emrin gerceklesebilecegi ilk gun: kapanistan once verildiyse bugun, sonra ise ertesi gun.

    Tatil gunu ayrica bilinmez; o gun endeks verisi olmadigi icin motor emri
    sonraki ilk islem gununde gerceklestirir.
    """
    local = now.astimezone(ZoneInfo(tz))
    if local.weekday() < 5 and local.time() < ORDER_CUTOFF:
        return local.date()
    return next_weekday(local.date())


def portfolio_start_day(now: datetime, tz: str) -> date:
    """Yeni portfoyun ilk islem gunu; kurallar manuel emirle aynidir."""
    return order_not_before(now, tz)


@dataclass(frozen=True)
class OrderDecision:
    action: Literal["fill", "hold", "reject"]
    plan: OrderPlan | None = None
    reason: str = ""


def decide_manual_order(
    *,
    ticker: str,
    side: str,
    quantity: Decimal | None,
    amount: Decimal | None,
    close: Decimal | None,
    day_change: Decimal,
    held: Decimal,
    cash: Decimal,
    waited_days: int,
) -> OrderDecision:
    """Bir manuel emrin bu islem gununun kapanisinda ne olacagi.

    "hold": emir beklemeye devam eder (hisse islem gormedi ya da tavan/tabanda
    kapandi); `ORDER_MAX_WAIT_DAYS` dolunca reddedilir.
    """
    expired = waited_days >= ORDER_MAX_WAIT_DAYS
    if close is None:
        if expired:
            return OrderDecision("reject", reason="Hisse bekleme süresince işlem görmedi.")
        return OrderDecision("hold")
    if side == "SELL":
        if held <= 0:
            return OrderDecision("reject", reason="Portföyde bu hisse yok.")
        if quantity is None or quantity > held:
            return OrderDecision(
                "reject", reason=f"Portföyde {held.normalize():f} adet var; daha fazlası satılamaz."
            )
        if day_change <= -PRICE_LIMIT_PCT:
            if expired:
                return OrderDecision("reject", reason="Hisse bekleme süresince tabanda kaldı.")
            return OrderDecision("hold")
        return OrderDecision("fill", plan_sell(ticker, close_price=close, quantity=quantity))

    if day_change >= PRICE_LIMIT_PCT:
        if expired:
            return OrderDecision("reject", reason="Hisse bekleme süresince tavanda kaldı.")
        return OrderDecision("hold")
    if quantity is not None:
        price = close * (Decimal(1) + SLIPPAGE_RATE)
        gross = _money(quantity * price)
        fee = _money(gross * FEE_RATE)
        if gross < MIN_TRADE_VALUE:
            return OrderDecision(
                "reject", reason=f"İşlem tutarı en az {MIN_TRADE_VALUE} TL olmalı."
            )
        if gross + fee > cash:
            return OrderDecision("reject", reason="Yetersiz nakit.")
        return OrderDecision("fill", OrderPlan(ticker, "BUY", quantity, price, gross, fee))
    plan = plan_buy(ticker, close_price=close, budget=amount or Decimal(0), cash=cash)
    if plan is None:
        return OrderDecision(
            "reject",
            reason=f"Tutar ya da nakit en az {MIN_TRADE_VALUE} TL'lik tam adet almaya yetmiyor.",
        )
    return OrderDecision("fill", plan)


# --- Veri yukleme ------------------------------------------------------------


async def _get_or_create_portfolio(
    session: AsyncSession, name: str, initial_cash: Decimal
) -> PaperPortfolio:
    portfolio = await session.scalar(
        select(PaperPortfolio).where(PaperPortfolio.name == name, PaperPortfolio.owner_id.is_(None))
    )
    if portfolio is not None:
        return portfolio
    portfolio = PaperPortfolio(
        name=name,
        kind="STRATEGY",
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


def portfolio_strategy(
    portfolio: PaperPortfolio, model_risk: RiskConfig
) -> tuple[StrategyParams, RiskConfig]:
    """Ayarli strateji portfoyu kendi esiklerini, digerleri model kurallarini kullanir."""
    if portfolio.kind == "STRATEGY" and portfolio.config:
        config = StrategyConfig.model_validate(portfolio.config)
        return config.params(), config.risk()
    return DEFAULT_PARAMS, model_risk


@dataclass(frozen=True)
class DayContext:
    """Bir islem gununun tum portfoylerce paylasilan, salt okunur verisi."""

    execution_date: date
    signal_date: date | None
    signals: list[Any]
    prices: dict[str, tuple[date, Decimal]]
    context: dict[str, tuple[Decimal | None, Decimal]]
    names: dict[str, str]


async def load_day_context(
    session: AsyncSession, execution_date: date, extra_tickers: set[str]
) -> DayContext:
    """Sinyaller + (sinyalli ve `extra_tickers` icin) fiyat, hacim ve sirket adlari."""
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
    price_tickers = {row.ticker for row in signals} | extra_tickers
    prices = await _latest_prices(session, price_tickers, execution_date)
    trade_tickers = {ticker for ticker, (day, _) in prices.items() if day == execution_date}
    names = dict(
        (
            await session.execute(
                select(Instrument.ticker, Instrument.name).where(
                    Instrument.ticker.in_(price_tickers)
                )
            )
        ).all()
    )
    context = await _execution_context(session, trade_tickers, execution_date)
    return DayContext(execution_date, signal_date, signals, prices, context, names)


# --- Kosu --------------------------------------------------------------------


async def run_paper_portfolios(
    *,
    as_of_date: date | None = None,
    factory: Callable[[], AsyncSession] | None = None,
) -> dict[str, Any]:
    """Model ve kullanici portfoylerinin islenmemis islem gunlerini isler.

    `as_of_date` verilirse yalniz o gun islenir (elle yeniden oynatma).
    """
    if factory is None:
        from app.core.db import session_factory as factory

    async with factory() as session:
        has_signals = await session.scalar(
            select(func.max(CompositeSignalSnapshot.as_of_date)).where(
                CompositeSignalSnapshot.model_version == SIGNAL_MODEL_VERSION
            )
        )
        if has_signals is None:
            return {"status": "no_signals", "portfolios": 0, "trades": 0}
        model = await _get_or_create_portfolio(
            session, DEFAULT_PORTFOLIO_NAME, DEFAULT_INITIAL_CASH
        )
        await session.commit()
        portfolios = (
            await session.execute(
                select(PaperPortfolio.id, PaperPortfolio.started_on).order_by(PaperPortfolio.id)
            )
        ).all()
        last_processed = dict(
            (
                await session.execute(
                    select(
                        PaperPortfolioSnapshot.portfolio_id,
                        func.max(PaperPortfolioSnapshot.snapshot_date),
                    ).group_by(PaperPortfolioSnapshot.portfolio_id)
                )
            ).all()
        )
        trading_days: list[date] = []
        if as_of_date is None:
            today = datetime.now(ZoneInfo(get_settings().tz)).date()
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
        model_risk = await load_risk_config()

    plan: dict[int, list[date]] = {}
    for portfolio_id, started_on in portfolios:
        if as_of_date is not None:
            days = [as_of_date] if started_on is None or as_of_date >= started_on else []
        else:
            eligible = [day for day in trading_days if started_on is None or day >= started_on]
            days = pending_execution_days(eligible, last_processed.get(portfolio_id))
        if days:
            plan[portfolio_id] = days

    failed: set[int] = set()
    model_results: list[dict[str, Any]] = []
    total_trades = 0
    processed = 0
    for day in sorted({day for days in plan.values() for day in days}):
        ids = [pid for pid, days in plan.items() if day in days and pid not in failed]
        if not ids:
            continue
        async with factory() as session:
            extra = set(
                (
                    await session.scalars(
                        select(PaperPosition.ticker)
                        .where(PaperPosition.portfolio_id.in_(ids))
                        .distinct()
                    )
                ).all()
            ) | set(
                (
                    await session.scalars(
                        select(PaperOrder.ticker)
                        .where(PaperOrder.portfolio_id.in_(ids), PaperOrder.status == "PENDING")
                        .distinct()
                    )
                ).all()
            )
            context = await load_day_context(session, day, extra)
        for portfolio_id in ids:
            async with factory() as session:
                try:
                    portfolio = await session.get(PaperPortfolio, portfolio_id)
                    if portfolio is None:  # bu arada silinmis
                        continue
                    params, risk = portfolio_strategy(portfolio, model_risk)
                    result = await _run_day(session, portfolio, context, params, risk)
                except Exception as exc:  # diger portfoyler islenmeye devam etsin
                    await session.rollback()
                    failed.add(portfolio_id)
                    logger.exception("paper_portfolio_failed", portfolio_id=portfolio_id, day=day)
                    await session.execute(
                        update(PaperPortfolio)
                        .where(PaperPortfolio.id == portfolio_id)
                        .values(last_error=f"{day.isoformat()}: {exc}"[:500])
                    )
                    await session.commit()
                    continue
            processed += 1
            total_trades += result["trades"]
            if portfolio_id == model.id:
                model_results.append(result)

    summary: dict[str, Any] = {
        "status": "partial" if failed else ("ok" if processed else "up_to_date"),
        "portfolios": len(plan),
        "portfolio_days": processed,
        "failed": len(failed),
        "trades": total_trades,
        "days": sorted({day.isoformat() for days in plan.values() for day in days}),
    }
    if model_results:
        summary["model"] = {
            **model_results[-1],
            "buys": sum(item["buys"] for item in model_results),
            "sells": sum(item["sells"] for item in model_results),
            "trades": sum(item["trades"] for item in model_results),
        }
    return summary


async def _fill_manual_orders(
    session: AsyncSession,
    portfolio: PaperPortfolio,
    day: DayContext,
    *,
    positions: dict[str, PaperPosition],
    trade_prices: dict[str, Decimal],
    change: Callable[[str], Decimal],
    cash: Decimal,
) -> tuple[Decimal, Decimal, Decimal, list[tuple[PaperOrder, PaperTrade]]]:
    """Bekleyen emirleri (once satislar) bugunun kapanisindan gerceklestirir.

    (nakit, gerceklesen K/Z degisimi, komisyon degisimi, (emir, islem) ciftleri)
    doner. Tamamen satilan pozisyonun adedi 0 olur; cagiran siler.
    """
    execution_date = day.execution_date
    orders = list(
        (
            await session.scalars(
                select(PaperOrder)
                .where(
                    PaperOrder.portfolio_id == portfolio.id,
                    PaperOrder.status == "PENDING",
                    PaperOrder.not_before <= execution_date,
                )
                .order_by(PaperOrder.id)
            )
        ).all()
    )
    orders.sort(key=lambda order: (order.side != "SELL", order.id))
    realized_delta = Decimal(0)
    fee_delta = Decimal(0)
    fills: list[tuple[PaperOrder, PaperTrade]] = []
    now = datetime.now(UTC)
    for order in orders:
        ticker = order.ticker
        position = positions.get(ticker)
        held = _decimal(position.quantity) if position is not None else Decimal(0)
        close = trade_prices.get(ticker)
        decision = decide_manual_order(
            ticker=ticker,
            side=order.side,
            quantity=None if order.quantity is None else _decimal(order.quantity),
            amount=None if order.amount is None else _decimal(order.amount),
            close=close,
            day_change=change(ticker) if close is not None else Decimal(0),
            held=held,
            cash=cash,
            waited_days=(execution_date - order.not_before).days,
        )
        if decision.action == "hold":
            continue
        if decision.action == "reject" or decision.plan is None:
            order.status = "REJECTED"
            order.note = decision.reason[:200] or "Emir gerçekleştirilemedi."
            continue
        plan = decision.plan
        assert close is not None
        realized: Decimal | None = None
        if plan.side == "SELL":
            assert position is not None
            average_cost = _decimal(position.average_cost)
            realized = _money(plan.gross_amount - plan.fee_amount - average_cost * plan.quantity)
            cash += plan.gross_amount - plan.fee_amount
            realized_delta += realized
            remaining = held - plan.quantity
            position.quantity = remaining
            position.market_value = _money(remaining * close)
            position.unrealized_pnl = _money((close - average_cost) * remaining)
        else:
            total_cost = plan.gross_amount + plan.fee_amount
            cash -= total_cost
            if position is None:
                position = PaperPosition(portfolio_id=portfolio.id, ticker=ticker)
                session.add(position)
                positions[ticker] = position
                held = Decimal(0)
            # Ayni hisseye ekleme: ortalama maliyet komisyon dahil agirlikli ortalamadir.
            previous_cost = held * _decimal(position.average_cost) if held > 0 else Decimal(0)
            quantity = held + plan.quantity
            average_cost = (previous_cost + total_cost) / quantity
            position.quantity = quantity
            position.average_cost = average_cost
            position.last_price = close
            position.high_water_price = max(close, average_cost)
            position.market_value = _money(quantity * close)
            position.unrealized_pnl = _money((close - average_cost) * quantity)
        fee_delta += plan.fee_amount
        trade = PaperTrade(
            execution_key=execution_key(
                portfolio.id, ticker, execution_date, f"ORDER{order.id}", MANUAL_VERSION
            ),
            portfolio_id=portfolio.id,
            ticker=ticker,
            signal_snapshot_id=None,
            strategy_version=MANUAL_VERSION,
            trade_date=execution_date,
            side=plan.side,
            quantity=plan.quantity,
            price=plan.price,
            gross_amount=plan.gross_amount,
            fee_amount=plan.fee_amount,
            realized_pnl=realized,
            reason=f"Manuel emir #{order.id}",
            exit_reason=None,
        )
        order.status = "FILLED"
        order.fill_price = plan.price
        order.filled_quantity = plan.quantity
        order.filled_at = now
        fills.append((order, trade))
    return cash, realized_delta, fee_delta, fills


async def _run_day(
    session: AsyncSession,
    portfolio: PaperPortfolio,
    day: DayContext,
    params: StrategyParams,
    risk: RiskConfig,
) -> dict[str, Any]:
    execution_date = day.execution_date
    signal_date = day.signal_date
    signals = day.signals
    signal_by_ticker = {row.ticker: row for row in signals}
    positions = list(
        (
            await session.scalars(
                select(PaperPosition).where(PaperPosition.portfolio_id == portfolio.id)
            )
        ).all()
    )
    position_by_ticker = {row.ticker: row for row in positions}
    mark_prices = {
        ticker: price
        for ticker, (price_date, price) in day.prices.items()
        if 0 <= (execution_date - price_date).days <= MAX_MARK_STALE_DAYS
    }
    # Islem yalniz o gunun kapanisiyla yapilir; islem gormeyen hisse eski fiyattan
    # alinip satilmaz (yalniz degerlenir).
    trade_prices = {
        ticker: price
        for ticker, (price_date, price) in day.prices.items()
        if price_date == execution_date
    }
    context = day.context

    def sector_of(ticker: str) -> str:
        return resolve_sector(ticker, day.names.get(ticker))

    def change(ticker: str) -> Decimal:
        return day_change_pct(trade_prices[ticker], context.get(ticker, (None, Decimal(0)))[0])

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

    fills: list[tuple[PaperOrder, PaperTrade]] = []
    if portfolio.kind == "MANUAL":
        version = MANUAL_VERSION
        if portfolio.status == "ACTIVE":
            cash, realized_delta, fee_delta, fills = await _fill_manual_orders(
                session,
                portfolio,
                day,
                positions=position_by_ticker,
                trade_prices=trade_prices,
                change=change,
                cash=cash,
            )
            realized_total += realized_delta
            fee_total += fee_delta
            trades.extend(trade for _, trade in fills)
            for ticker, position in list(position_by_ticker.items()):
                if _decimal(position.quantity) <= 0:
                    await session.delete(position)
                    closed.add(ticker)
    else:
        version = STRATEGY_VERSION
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
        marked_equity = cash + sum(
            (_decimal(position.market_value) for position in position_by_ticker.values()),
            Decimal(0),
        )

        # Cikislar: zarar-kes / trailing / kar-al / sinyal / rebalance (bugun satilmislar atlanir).
        actions = (
            plan_position_actions(
                states,
                scores={
                    ticker: _decimal(row.composite_score)
                    for ticker, row in signal_by_ticker.items()
                },
                exit_score=params.exit_score,
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
            ticker: position
            for ticker, position in position_by_ticker.items()
            if ticker not in closed
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
                slots=entry_slots(
                    open_count=len(open_positions), bought_today=len(bought_today), params=params
                ),
                params=params,
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
                position_by_ticker[signal.ticker] = position
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
                            f"Bileşik skor {float(signal.composite_score):.1f} ≥ "
                            f"{params.entry_score}; "
                            f"güven %{float(signal.confidence) * 100:.0f}; "
                            f"sinyal {signal_date:%d.%m.%Y}"
                        ),
                        exit_reason=None,
                    )
                )

    open_positions = {
        ticker: position for ticker, position in position_by_ticker.items() if ticker not in closed
    }
    if trades:
        session.add_all(trades)
    portfolio.cash_balance = _money(cash)
    portfolio.realized_pnl = _money(realized_total)
    portfolio.total_fees = _money(fee_total)
    portfolio.strategy_version = version
    portfolio.last_run_at = datetime.now(UTC)
    portfolio.last_error = None
    await session.flush()
    for order, trade in fills:
        order.trade_id = trade.id

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
        "strategy_version": version,
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
