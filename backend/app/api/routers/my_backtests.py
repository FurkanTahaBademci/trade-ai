"""Kullanicinin kendi backtest kosulari: baslatma (kotali), sonuc, islemler ve paper koprusu.

Kosu kuyruga yazilir ve worker'da tek tek hesaplanir; istek beklemez. Baskasinin
kosusu 404 doner.
"""

from datetime import UTC, datetime, time
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.backtests import run_trades
from app.api.routers.my_portfolios import create_portfolio
from app.auth.deps import CurrentAuth
from app.backtest.service import fail_stale_runs, get_backtest_run, queue_backtest_run
from app.core.config import get_settings
from app.core.db import get_db
from app.models import BacktestRun, BacktestRunTrade
from app.paper.strategy import StrategyConfig
from app.schemas.backtest import (
    BacktestCreate,
    BacktestQuotaOut,
    BacktestRunDetailOut,
    BacktestRunSummaryOut,
    BacktestToPaperIn,
    BacktestTradeOut,
)
from app.schemas.paper import MyPortfolioCreate, MyPortfolioOut

router = APIRouter(prefix="/api/me/backtests", tags=["my-backtests"])
DB = Annotated[AsyncSession, Depends(get_db)]
ACTIVE_STATUSES = ("QUEUED", "RUNNING")


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


async def _owned(
    db: AsyncSession, user_id: int, run_id: int, *, include_trades: bool
) -> BacktestRun:
    run = await get_backtest_run(db, run_id, include_trades=include_trades)
    if run is None or run.owner_id != user_id:
        raise _error(404, "not_found", "Backtest koşusu bulunamadı.")
    return run


async def _quota(db: AsyncSession, user_id: int, *, exempt: bool) -> BacktestQuotaOut:
    # Takili kalmis kosu (worker yeniden baslatildi vb.) kullaniciyi kilitlemesin.
    if await fail_stale_runs(db):
        await db.commit()
    settings = get_settings()
    tz = ZoneInfo(settings.tz)
    # Gun, Istanbul saatiyle baslar; karsilastirma UTC zaman damgasiyla yapilir.
    day_start = datetime.combine(datetime.now(tz).date(), time.min, tzinfo=tz).astimezone(UTC)
    used_today, active = (
        await db.execute(
            select(
                func.count(BacktestRun.id).filter(BacktestRun.created_at >= day_start),
                func.count(BacktestRun.id).filter(BacktestRun.status.in_(ACTIVE_STATUSES)),
            ).where(BacktestRun.owner_id == user_id)
        )
    ).one()
    return BacktestQuotaOut(
        daily_limit=settings.backtest_daily_limit_per_user,
        used_today=used_today or 0,
        active=active or 0,
        max_active=settings.backtest_max_active_per_user,
        exempt=exempt,
    )


def paper_config_from_backtest(config: dict) -> StrategyConfig:
    """Esik stratejili kosunun ayarlarini strateji portfoyu ayarina cevirir.

    Backtest'te olmayan kurallar (kar-al, takip eden stop, sektor tavani,
    yeniden dengeleme) kapali gelir; komisyon, kayma, tavan/taban ve hacim
    kurallari paper'da herkes icin sabittir.
    """
    if config.get("strategy", "threshold") != "threshold":
        raise ValueError(
            "Sıralama sepeti stratejisi paper portföyde yok; eşik stratejisiyle koşulan testi kullan."
        )
    if config.get("component_weights"):
        raise ValueError(
            "Ağırlık simülasyonlu test paper portföye aktarılamaz; paper portföy canlı bileşik "
            "skoru kullanır."
        )
    max_positions = int(config.get("max_positions", 10))
    daily = int(config.get("max_new_entries_per_day", 3)) or max_positions
    try:
        return StrategyConfig(
            entry_score=config.get("entry_score", 75),
            exit_score=config.get("exit_score", 55),
            min_confidence=config.get("min_confidence", 0.25),
            min_coverage=config.get("min_coverage", 2),
            max_positions=max_positions,
            max_new_entries_per_day=min(daily, 30),
            max_position_weight_pct=round(float(config.get("max_position_weight", 0.1)) * 100, 4),
            max_sector_weight_pct=0,
            stop_loss_pct=config.get("stop_loss_pct", 15),
            take_profit_pct=0,
            trailing_stop_pct=0,
            rebalance_enabled=False,
        )
    except ValidationError as exc:
        raise ValueError(
            "Bu ayarlar paper portföy sınırlarının dışında (en fazla 30 pozisyon, giriş skoru "
            "en az 50, tek pozisyon tavanı en çok %50)."
        ) from exc


@router.get("/quota", response_model=BacktestQuotaOut)
async def my_quota(auth: CurrentAuth, db: DB) -> BacktestQuotaOut:
    return await _quota(db, auth.user.id, exempt=auth.user.role == "admin")


@router.get("", response_model=list[BacktestRunSummaryOut])
async def list_my_runs(
    auth: CurrentAuth,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    before_id: Annotated[int | None, Query(ge=1)] = None,
) -> list[BacktestRun]:
    stmt = select(BacktestRun).where(BacktestRun.owner_id == auth.user.id)
    if before_id is not None:
        stmt = stmt.where(BacktestRun.id < before_id)
    return list((await db.scalars(stmt.order_by(BacktestRun.id.desc()).limit(limit))).all())


@router.post("", response_model=BacktestRunDetailOut, status_code=status.HTTP_202_ACCEPTED)
async def start_my_run(payload: BacktestCreate, auth: CurrentAuth, db: DB) -> BacktestRun:
    exempt = auth.user.role == "admin"
    if not exempt:
        quota = await _quota(db, auth.user.id, exempt=False)
        if quota.active >= quota.max_active:
            raise _error(
                409,
                "active_run",
                "Önceki koşun bitmeden yenisini başlatamazsın; sonuç birkaç dakika içinde gelir.",
            )
        if quota.used_today >= quota.daily_limit:
            raise _error(
                429,
                "daily_limit",
                f"Günlük {quota.daily_limit} backtest hakkını kullandın; yarın yeniden deneyebilirsin.",
            )
    return await queue_backtest_run(db, payload, owner_id=auth.user.id)


@router.get("/{run_id}", response_model=BacktestRunDetailOut)
async def get_my_run(
    run_id: int, auth: CurrentAuth, db: DB, include_trades: bool = True
) -> BacktestRun:
    return await _owned(db, auth.user.id, run_id, include_trades=include_trades)


@router.get("/{run_id}/trades", response_model=list[BacktestTradeOut])
async def my_run_trades(
    run_id: int,
    auth: CurrentAuth,
    db: DB,
    ticker: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
    side: Literal["BUY", "SELL"] | None = None,
    before_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[BacktestRunTrade]:
    await _owned(db, auth.user.id, run_id, include_trades=False)
    return await run_trades(db, run_id, ticker=ticker, side=side, before_id=before_id, limit=limit)


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_run(run_id: int, auth: CurrentAuth, db: DB) -> Response:
    run = await _owned(db, auth.user.id, run_id, include_trades=False)
    if run.status == "RUNNING":
        raise _error(409, "running", "Çalışan koşu silinemez; bitmesini bekle.")
    await db.delete(run)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{run_id}/paper", response_model=MyPortfolioOut, status_code=status.HTTP_201_CREATED)
async def start_paper_from_run(
    run_id: int, body: BacktestToPaperIn, auth: CurrentAuth, db: DB
) -> MyPortfolioOut:
    run = await _owned(db, auth.user.id, run_id, include_trades=False)
    if run.status != "COMPLETED":
        raise _error(422, "not_completed", "Yalnız tamamlanmış koşunun ayarları aktarılabilir.")
    try:
        config = paper_config_from_backtest(run.config or {})
    except ValueError as exc:
        raise _error(422, "unsupported", str(exc)) from exc
    return await create_portfolio(
        db,
        auth.user.id,
        MyPortfolioCreate(
            name=body.name, kind="STRATEGY", initial_cash=body.initial_cash, config=config
        ),
    )
