"""ARQ cron/is fonksiyonlari.

Her fonksiyon `(ctx)` imzasi alir (ARQ konvansiyonu). Asil is mantigi
`app/collectors/*.py` icinde; burada sadece DB session acilip collector
cagriliyor. Boylece collector'lar hem CLI'dan (`scripts/run_once.py`) hem
worker'dan ayni kod yolunu kullanir.
"""

import contextlib
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from redis.exceptions import RedisError

from app.core.db import session_factory
from app.core.redis import get_redis

logger = structlog.get_logger(__name__)


async def collect_instruments(ctx: dict) -> dict:
    from app.collectors.instruments import InstrumentCollector

    async with session_factory() as session, InstrumentCollector(session) as collector:
        return await collector.run_tracked()


async def collect_prices(
    ctx: dict | None = None, *, days: int | None = None, backfill: bool = False
) -> dict:
    from sqlalchemy import func, select

    from app.collectors.prices import DEFAULT_BACKFILL_YEARS, PriceCollector
    from app.models import PriceDaily

    today = datetime.now(ZoneInfo("Europe/Istanbul")).date()

    async with session_factory() as session:
        count_res = await session.execute(select(func.count(PriceDaily.id)))
        row_count = count_res.scalar() or 0

        if days is not None:
            start_date = today - timedelta(days=days)
        elif backfill or row_count < 5000:
            logger.info("price_history_backfill_active", current_rows=row_count)
            start_date = today - timedelta(days=365 * DEFAULT_BACKFILL_YEARS)
        else:
            # Tatil ve duzeltmeler icin 10 gunluk pay
            start_date = today - timedelta(days=10)

        async with PriceCollector(session, start_date=start_date) as collector:
            return await collector.run_tracked()


# Bu kadar satirdan azsa XU100 gecmisi eksik sayilir (~1,5 yil islem gunu).
INDEX_BACKFILL_MIN_ROWS = 400
# Endeks gecmisi yokken hesaplanan skorlarda momentum (20/60 islem gunu) eksikti;
# endeksin eski ilk gununden bu kadar sonrasina kadar olan skor gunleri yenilenir.
INDEX_MOMENTUM_WARMUP_DAYS = 100


async def collect_index_prices(ctx: dict) -> dict:
    from sqlalchemy import func, select

    from app.collectors.index_prices import IndexPriceCollector
    from app.models import IndexDaily
    from app.signals.service import BENCHMARK_INDEX, MODEL_VERSION

    today = datetime.now(ZoneInfo("Europe/Istanbul")).date()
    async with session_factory() as session:
        row_count, first_day = (
            await session.execute(
                select(func.count(IndexDaily.id), func.min(IndexDaily.date)).where(
                    IndexDaily.index_code == BENCHMARK_INDEX
                )
            )
        ).one()
    # prices.py ile ayni desen: gecmis eksikse bir kez uzun doldurma, sonra her
    # kosuda yalniz son birkac gun (duzeltilmis kapanislar icin pay birakildi).
    # Skor gecmisi, momentum ve backtest islem gunu takvimi olarak XU100'u kullanir.
    backfill = row_count < INDEX_BACKFILL_MIN_ROWS
    start_date = None if backfill else today - timedelta(days=5)
    if backfill:
        logger.info("index_history_backfill_active", current_rows=row_count)
    async with (
        session_factory() as session,
        IndexPriceCollector(session, start_date=start_date) as collector,
    ):
        result = await collector.run_tracked()

    if backfill and first_day is not None and result.get("rows_upserted", 0) > row_count:
        # Endeks gecmisi eksikken hesaplanmis gunler (momentumsuz) worker'in
        # gecmis doldurma adiminda yeniden hesaplanir (bkz. compute_signals).
        redis = get_redis()
        refresh_until = first_day + timedelta(days=INDEX_MOMENTUM_WARMUP_DAYS)
        with contextlib.suppress(RedisError):
            await redis.delete(f"signals:backfill:attempted:{MODEL_VERSION}")
            await redis.set(
                f"signals:backfill:refresh_until:{MODEL_VERSION}", refresh_until.isoformat()
            )
        result = {**result, "signal_refresh_until": refresh_until.isoformat()}
    return result


async def collect_kap(ctx: dict) -> dict:
    from app.collectors.kap import KapCollector

    # Uc gunluk kayan pencere hafta sonu/tatil ve gecici KAP kesintilerini
    # telafi eder. disclosure_index upsert'i nedeniyle tekrarlar zararsizdir.
    async with session_factory() as session, KapCollector(session, lookback_days=3) as collector:
        return await collector.run_tracked()


async def collect_news(ctx: dict) -> dict:
    from app.collectors.news import NewsCollector

    async with session_factory() as session, NewsCollector(session) as collector:
        return await collector.run_tracked()


async def evaluate_sources(ctx: dict) -> dict:
    from app.llm.service import run_llm_evaluations

    async with session_factory() as session:
        return await run_llm_evaluations(session)


async def collect_fundamentals(ctx: dict) -> dict:
    from app.collectors.fundamentals import FundamentalsCollector

    # Ticker verilmezse collector son 30 gunun ilgili LLM ciktilarindan en
    # fazla 50 aktif BIST kodunu secer; tum evreni maliyetli sekilde taramaz.
    async with session_factory() as session, FundamentalsCollector(session) as collector:
        return await collector.run_tracked()


async def collect_analysts(ctx: dict) -> dict:
    from app.collectors.analysts import AnalystCollector

    async with session_factory() as session, AnalystCollector(session) as collector:
        return await collector.run_tracked()


async def collect_fund_flows(ctx: dict) -> dict:
    from app.collectors.fund_flows import FundFlowCollector

    async with session_factory() as session, FundFlowCollector(session) as collector:
        return await collector.run_tracked()


async def collect_institutional_reports(ctx: dict) -> dict:
    from app.collectors.institutional_reports import InstitutionalReportCollector

    async with (
        session_factory() as session,
        InstitutionalReportCollector(session) as collector,
    ):
        return await collector.run_tracked()


async def compute_signals(ctx: dict) -> dict:
    from app.signals.reports import refresh_reports_if_stale
    from app.signals.service import (
        MODEL_VERSION,
        missing_signal_days,
        run_signal_engine,
        select_backfill_days,
    )

    async with session_factory() as session:
        result = await run_signal_engine(session)
        trading_days, existing_days = await missing_signal_days(
            session, today=date.fromisoformat(result["as_of_date"])
        )

    # Eksik gecmis gunlerden kucuk bir parti; her gun o tarihte bilinen veriyle
    # hesaplanir ve upsert oldugu icin tekrar calismasi zararsizdir.
    attempted_key = f"signals:backfill:attempted:{MODEL_VERSION}"
    refresh_key = f"signals:backfill:refresh_until:{MODEL_VERSION}"
    redis = get_redis()
    try:
        attempted = {date.fromisoformat(item) for item in await redis.smembers(attempted_key)}
        refresh_raw = await redis.get(refresh_key)
        refresh_until = date.fromisoformat(refresh_raw) if refresh_raw else None
    except (RedisError, ValueError):
        attempted, refresh_until = set(), None
    if refresh_until is not None:
        # Endeks gecmisi sonradan dolduruldu: o tarihe kadarki skorlar eksik
        # (momentumsuz) hesaplanmisti; bu gunler bir kez yeniden hesaplanir.
        existing_days = {day for day in existing_days if day > refresh_until}
    days, remaining = select_backfill_days(trading_days, existing_days, attempted)
    for day in days:
        async with session_factory() as session:
            await run_signal_engine(session, as_of_date=day)
        with contextlib.suppress(RedisError):
            await redis.sadd(attempted_key, day.isoformat())
    if refresh_until is not None and remaining == 0:
        with contextlib.suppress(RedisError):
            await redis.delete(refresh_key)
    if days:
        logger.info(
            "signals_history_backfill",
            days=[day.isoformat() for day in days],
            remaining=remaining,
        )
    # Dogruluk ve bilesen gucu raporlari kullanici isteginde degil burada hesaplanir.
    async with session_factory() as session:
        reports_refreshed = await refresh_reports_if_stale(session)
    return {
        **result,
        "backfilled_days": len(days),
        "backfill_remaining": remaining,
        "reports_refreshed": reports_refreshed,
    }


async def run_paper_portfolio(ctx: dict) -> dict:
    from app.paper.service import run_paper_portfolio as execute_paper_portfolio

    async with session_factory() as session:
        return await execute_paper_portfolio(session)


async def collect_evds(ctx: dict) -> dict:
    from app.collectors.evds import EvdsCollector

    async with session_factory() as session, EvdsCollector(session) as collector:
        return await collector.run_tracked()


async def collect_tcmb_policy(ctx: dict) -> dict:
    from app.collectors.tcmb_policy import TcmbPolicyCollector

    async with session_factory() as session, TcmbPolicyCollector(session) as collector:
        return await collector.run_tracked()
