"""Kullanicinin kendi paper portfoyleri: olusturma, ayarlar, performans ve manuel emirler.

Her uc oturum ister ve yalniz o kullanicinin portfoylerine erisir; baskasinin
portfoy kimligi 404 doner (varligi da sizdirilmaz).
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.paper import performance_of, positions_of, risk_of, trades_csv, trades_of
from app.auth.deps import CurrentAuth
from app.core.config import get_settings
from app.core.db import get_db
from app.models import Instrument, PaperOrder, PaperPortfolio, PaperPortfolioSnapshot, PaperPosition
from app.paper.service import (
    MANUAL_VERSION,
    STRATEGY_VERSION,
    load_risk_config,
    order_not_before,
    portfolio_start_day,
    portfolio_strategy,
)
from app.paper.strategy import TEMPLATES
from app.schemas.paper import (
    MyPortfolioCreate,
    MyPortfolioOut,
    MyPortfolioSummaryOut,
    MyPortfolioUpdate,
    PaperOrderCreate,
    PaperOrderOut,
    PaperPortfolioSnapshotOut,
    PaperPositionOut,
    PaperRiskOut,
    PaperTradeOut,
    StrategyTemplateOut,
)

router = APIRouter(prefix="/api/me/portfolios", tags=["my-portfolios"])
DB = Annotated[AsyncSession, Depends(get_db)]


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


async def owned_portfolio(db: AsyncSession, user_id: int, portfolio_id: int) -> PaperPortfolio:
    portfolio = await db.get(PaperPortfolio, portfolio_id)
    if portfolio is None or portfolio.owner_id != user_id:
        raise _error(404, "not_found", "Portföy bulunamadı.")
    return portfolio


def _portfolio_out(portfolio: PaperPortfolio) -> MyPortfolioOut:
    return MyPortfolioOut.model_validate(portfolio, from_attributes=True)


@router.get("/templates", response_model=list[StrategyTemplateOut])
async def list_templates() -> list[StrategyTemplateOut]:
    return [
        StrategyTemplateOut(
            key=item.key, label=item.label, description=item.description, config=item.config
        )
        for item in TEMPLATES.values()
    ]


@router.get("", response_model=list[MyPortfolioSummaryOut])
async def list_my_portfolios(auth: CurrentAuth, db: DB) -> list[MyPortfolioSummaryOut]:
    portfolios = list(
        (
            await db.scalars(
                select(PaperPortfolio)
                .where(PaperPortfolio.owner_id == auth.user.id)
                .order_by(PaperPortfolio.id)
            )
        ).all()
    )
    ids = [row.id for row in portfolios]
    latest = (
        select(
            PaperPortfolioSnapshot.portfolio_id,
            func.max(PaperPortfolioSnapshot.snapshot_date).label("snapshot_date"),
        )
        .where(PaperPortfolioSnapshot.portfolio_id.in_(ids))
        .group_by(PaperPortfolioSnapshot.portfolio_id)
        .subquery()
    )
    snapshots = {
        row.portfolio_id: row
        for row in (
            await db.scalars(
                select(PaperPortfolioSnapshot).join(
                    latest,
                    (latest.c.portfolio_id == PaperPortfolioSnapshot.portfolio_id)
                    & (latest.c.snapshot_date == PaperPortfolioSnapshot.snapshot_date),
                )
            )
        ).all()
    }
    pending = dict(
        (
            await db.execute(
                select(PaperOrder.portfolio_id, func.count(PaperOrder.id))
                .where(PaperOrder.portfolio_id.in_(ids), PaperOrder.status == "PENDING")
                .group_by(PaperOrder.portfolio_id)
            )
        ).all()
    )
    result = []
    for portfolio in portfolios:
        snapshot = snapshots.get(portfolio.id)
        base = _portfolio_out(portfolio).model_dump()
        result.append(
            MyPortfolioSummaryOut(
                **base,
                total_equity=float(snapshot.total_equity)
                if snapshot
                else float(portfolio.cash_balance),
                total_return_pct=float(snapshot.total_return_pct) if snapshot else 0.0,
                position_count=snapshot.position_count if snapshot else 0,
                snapshot_date=snapshot.snapshot_date if snapshot else None,
                pending_orders=pending.get(portfolio.id, 0),
            )
        )
    return result


@router.post("", response_model=MyPortfolioOut, status_code=status.HTTP_201_CREATED)
async def create_my_portfolio(body: MyPortfolioCreate, auth: CurrentAuth, db: DB) -> MyPortfolioOut:
    settings = get_settings()
    count = await db.scalar(
        select(func.count(PaperPortfolio.id)).where(PaperPortfolio.owner_id == auth.user.id)
    )
    if (count or 0) >= settings.paper_max_portfolios_per_user:
        raise _error(
            409,
            "portfolio_limit",
            f"En fazla {settings.paper_max_portfolios_per_user} portföy açabilirsin; "
            "yenisi için birini sil.",
        )
    config = None
    if body.kind == "STRATEGY":
        config = body.config or TEMPLATES[body.template or "model"].config
    cash = Decimal(str(body.initial_cash))
    portfolio = PaperPortfolio(
        owner_id=auth.user.id,
        name=body.name.strip(),
        kind=body.kind,
        config=config.model_dump() if config else None,
        started_on=portfolio_start_day(datetime.now(UTC), settings.tz),
        strategy_version=STRATEGY_VERSION if body.kind == "STRATEGY" else MANUAL_VERSION,
        base_currency="TRY",
        status="ACTIVE",
        initial_cash=cash,
        cash_balance=cash,
        realized_pnl=Decimal(0),
        total_fees=Decimal(0),
    )
    db.add(portfolio)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _error(409, "duplicate_name", "Bu adla bir portföyün zaten var.") from exc
    await db.refresh(portfolio)
    return _portfolio_out(portfolio)


@router.get("/{portfolio_id}", response_model=MyPortfolioOut)
async def get_my_portfolio(portfolio_id: int, auth: CurrentAuth, db: DB) -> MyPortfolioOut:
    return _portfolio_out(await owned_portfolio(db, auth.user.id, portfolio_id))


@router.patch("/{portfolio_id}", response_model=MyPortfolioOut)
async def update_my_portfolio(
    portfolio_id: int, body: MyPortfolioUpdate, auth: CurrentAuth, db: DB
) -> MyPortfolioOut:
    portfolio = await owned_portfolio(db, auth.user.id, portfolio_id)
    if body.name is not None:
        portfolio.name = body.name.strip()
    if body.status is not None:
        portfolio.status = body.status
    if body.config is not None:
        if portfolio.kind != "STRATEGY":
            raise _error(422, "not_strategy", "Manuel portföyün strateji ayarı yoktur.")
        # Yeni esikler bir sonraki islem gunu kosusundan itibaren gecerlidir.
        portfolio.config = body.config.model_dump()
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _error(409, "duplicate_name", "Bu adla bir portföyün zaten var.") from exc
    await db.refresh(portfolio)
    return _portfolio_out(portfolio)


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_portfolio(portfolio_id: int, auth: CurrentAuth, db: DB) -> Response:
    portfolio = await owned_portfolio(db, auth.user.id, portfolio_id)
    await db.delete(portfolio)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{portfolio_id}/positions", response_model=list[PaperPositionOut])
async def my_positions(portfolio_id: int, auth: CurrentAuth, db: DB) -> list[PaperPosition]:
    await owned_portfolio(db, auth.user.id, portfolio_id)
    return await positions_of(db, portfolio_id)


@router.get("/{portfolio_id}/trades", response_model=list[PaperTradeOut])
async def my_trades(
    portfolio_id: int,
    auth: CurrentAuth,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=1_000)] = 100,
):
    await owned_portfolio(db, auth.user.id, portfolio_id)
    return await trades_of(db, portfolio_id, None, limit)


@router.get("/{portfolio_id}/trades.csv")
async def my_trades_csv(portfolio_id: int, auth: CurrentAuth, db: DB):
    await owned_portfolio(db, auth.user.id, portfolio_id)
    return trades_csv(portfolio_id, await trades_of(db, portfolio_id, None, 1_000))


@router.get("/{portfolio_id}/performance", response_model=list[PaperPortfolioSnapshotOut])
async def my_performance(
    portfolio_id: int,
    auth: CurrentAuth,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=1_000)] = 365,
):
    await owned_portfolio(db, auth.user.id, portfolio_id)
    return await performance_of(db, portfolio_id, limit)


@router.get("/{portfolio_id}/risk", response_model=PaperRiskOut)
async def my_risk(portfolio_id: int, auth: CurrentAuth, db: DB) -> dict:
    portfolio = await owned_portfolio(db, auth.user.id, portfolio_id)
    cfg = None
    if portfolio.kind == "STRATEGY":
        _, cfg = portfolio_strategy(portfolio, await load_risk_config())
    return await risk_of(db, portfolio, cfg)


@router.get("/{portfolio_id}/orders", response_model=list[PaperOrderOut])
async def my_orders(
    portfolio_id: int,
    auth: CurrentAuth,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    await owned_portfolio(db, auth.user.id, portfolio_id)
    rows = await db.scalars(
        select(PaperOrder)
        .where(PaperOrder.portfolio_id == portfolio_id)
        .order_by(PaperOrder.id.desc())
        .limit(limit)
    )
    return list(rows.all())


@router.post(
    "/{portfolio_id}/orders", response_model=PaperOrderOut, status_code=status.HTTP_201_CREATED
)
async def place_order(
    portfolio_id: int, body: PaperOrderCreate, auth: CurrentAuth, db: DB
) -> PaperOrder:
    portfolio = await owned_portfolio(db, auth.user.id, portfolio_id)
    if portfolio.kind != "MANUAL":
        raise _error(
            422, "not_manual", "Strateji portföyü emir almaz; işlemleri sinyal kuralları yapar."
        )
    if portfolio.status != "ACTIVE":
        raise _error(422, "paused", "Duraklatılmış portföye emir verilemez.")
    ticker = body.ticker.strip().upper()
    instrument = await db.get(Instrument, ticker)
    if instrument is None or not instrument.is_active:
        raise _error(422, "unknown_ticker", f"{ticker} işlem gören bir BIST hissesi değil.")
    if body.client_order_id:
        existing = await db.scalar(
            select(PaperOrder).where(
                PaperOrder.portfolio_id == portfolio_id,
                PaperOrder.client_order_id == body.client_order_id,
            )
        )
        if existing is not None:  # ayni formun ikinci gonderimi
            return existing
    pending = list(
        (
            await db.scalars(
                select(PaperOrder).where(
                    PaperOrder.portfolio_id == portfolio_id, PaperOrder.status == "PENDING"
                )
            )
        ).all()
    )
    limit = get_settings().paper_max_pending_orders
    if len(pending) >= limit:
        raise _error(409, "order_limit", f"En fazla {limit} bekleyen emir olabilir.")
    if body.side == "SELL":
        held = await db.scalar(
            select(PaperPosition.quantity).where(
                PaperPosition.portfolio_id == portfolio_id, PaperPosition.ticker == ticker
            )
        )
        reserved = sum(
            (row.quantity or 0 for row in pending if row.side == "SELL" and row.ticker == ticker),
            Decimal(0),
        )
        available = Decimal(held or 0) - reserved
        if (body.quantity or 0) > available:
            raise _error(
                422,
                "insufficient_shares",
                f"Satılabilir {ticker} adedi: {available.normalize():f}"
                + (" (bekleyen satışlar düşüldü)." if reserved else "."),
            )
    order = PaperOrder(
        portfolio_id=portfolio_id,
        ticker=ticker,
        side=body.side,
        quantity=Decimal(body.quantity) if body.quantity is not None else None,
        amount=Decimal(str(body.amount)) if body.amount is not None else None,
        status="PENDING",
        client_order_id=body.client_order_id,
        not_before=order_not_before(datetime.now(UTC), get_settings().tz),
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@router.delete("/{portfolio_id}/orders/{order_id}", response_model=PaperOrderOut)
async def cancel_order(portfolio_id: int, order_id: int, auth: CurrentAuth, db: DB) -> PaperOrder:
    await owned_portfolio(db, auth.user.id, portfolio_id)
    order = await db.get(PaperOrder, order_id)
    if order is None or order.portfolio_id != portfolio_id:
        raise _error(404, "not_found", "Emir bulunamadı.")
    if order.status != "PENDING":
        raise _error(409, "not_pending", "Yalnız bekleyen emir iptal edilebilir.")
    order.status = "CANCELLED"
    order.note = "Kullanıcı iptal etti."
    await db.commit()
    await db.refresh(order)
    return order
