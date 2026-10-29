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


# Bundan az fiyat satiri varsa ilk kurulum doldurmasi yapilir.
PRICE_BACKFILL_MIN_ROWS = 5000


async def collect_prices(
    ctx: dict | None = None, *, days: int | None = None, backfill: bool = False
) -> dict:
    from sqlalchemy import func, select

    from app.collectors.prices import DEFAULT_BACKFILL_YEARS, PriceCollector
    from app.models import PriceDaily

    today = datetime.now(ZoneInfo("Europe/Istanbul")).date()

    async with session_factory() as session:
        # Yalniz "5000'den az mi" sorusu sorulur; tum tablo sayilmaz.
        count_res = await session.execute(
            select(func.count()).select_from(
                select(PriceDaily.id).limit(PRICE_BACKFILL_MIN_ROWS).subquery()
            )
        )
        row_count = count_res.scalar() or 0

        if days is not None:
            start_date = today - timedelta(days=days)
        elif backfill or row_count < PRICE_BACKFILL_MIN_ROWS:
            logger.info("price_history_backfill_active", current_rows=row_count)
            start_date = today - timedelta(days=365 * DEFAULT_BACKFILL_YEARS)
        else:
            # Tatil ve duzeltmeler icin 10 gunluk pay
            start_date = today - timedelta(days=10)

        async with PriceCollector(session, start_date=start_date) as collector:
            result = await collector.run_tracked()
    if days is not None or backfill:
        return result
    return {**result, "history_backfill": await _backfill_short_price_histories(today)}


# Ilk fiyati bundan yeni olan aktif hissenin gecmisi eksik sayilir. Toplam satir
# sayisina bakan ilk kurulum doldurmasi yarida kalirsa hisselerin cogu yalniz
# birkac haftalik fiyatla kaliyordu (grafik, momentum ve backtest bundan etkilenir).
PRICE_HISTORY_MIN_DAYS = 730
# Yeni halka arzlar gibi kaynakta da kisa gecmisi olan hisseler her gun denenmesin.
PRICE_BACKFILL_RETRY_SECONDS = 30 * 24 * 60 * 60


async def _short_history_tickers(today: date) -> list[str]:
    from sqlalchemy import select

    from app.models import Instrument, PriceDaily

    # "Ilk fiyat esikten yeni (veya hic fiyat yok)" == "esikte/oncesinde fiyat yok".
    # NOT EXISTS her aktif hisse icin (ticker, date) indeksine tek bakis yapar;
    # GROUP BY ile tum price_daily taranmaz.
    old_price_exists = (
        select(PriceDaily.id)
        .where(
            PriceDaily.ticker == Instrument.ticker,
            PriceDaily.date <= today - timedelta(days=PRICE_HISTORY_MIN_DAYS),
        )
        .exists()
    )
    async with session_factory() as session:
        return list(
            (
                await session.scalars(
                    select(Instrument.ticker)
                    .where(Instrument.is_active.is_(True), ~old_price_exists)
                    .order_by(Instrument.ticker)
                )
            ).all()
        )


async def _backfill_short_price_histories(today: date) -> dict:
    from app.collectors.prices import DEFAULT_BACKFILL_YEARS, PriceCollector
    from app.signals.service import MODEL_VERSION

    candidates = await _short_history_tickers(today)
    if not candidates:
        return {"tickers": 0}
    redis = get_redis()
    try:
        flags = await redis.mget([f"prices:backfill:attempted:{ticker}" for ticker in candidates])
    except RedisError:
        flags = [None] * len(candidates)
    tickers = [ticker for ticker, flag in zip(candidates, flags, strict=True) if not flag]
    if not tickers:
        return {"tickers": 0, "waiting": len(candidates)}
    logger.info("price_history_ticker_backfill", tickers=len(tickers))
    async with (
        session_factory() as session,
        PriceCollector(
            session,
            tickers=tickers,
            start_date=today - timedelta(days=365 * DEFAULT_BACKFILL_YEARS),
        ) as collector,
    ):
        result = await collector.run()
    with contextlib.suppress(RedisError):
        for ticker in tickers:
            await redis.set(
                f"prices:backfill:attempted:{ticker}", "1", ex=PRICE_BACKFILL_RETRY_SECONDS
            )
        if result.get("rows_upserted", 0) > 0:
            # Fiyat gecmisi olmadan (momentumsuz) hesaplanmis skor gunleri bir kez
            # yeniden hesaplanir (bkz. compute_signals).
            await redis.delete(f"signals:backfill:attempted:{MODEL_VERSION}")
            await redis.set(f"signals:backfill:refresh_until:{MODEL_VERSION}", today.isoformat())
    return {
        "tickers": len(tickers),
        "rows_upserted": result.get("rows_upserted", 0),
        "failed": len(result.get("failed_tickers", [])),
    }


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
    from app.paper.service import run_paper_portfolios

    # Model ve kullanici portfoyleri; her portfoy kendi oturumunda islenir.
    return await run_paper_portfolios()


async def collect_evds(ctx: dict) -> dict:
    from app.collectors.evds import EvdsCollector

    async with session_factory() as session, EvdsCollector(session) as collector:
        return await collector.run_tracked()


async def collect_tcmb_policy(ctx: dict) -> dict:
    from app.collectors.tcmb_policy import TcmbPolicyCollector

    async with session_factory() as session, TcmbPolicyCollector(session) as collector:
        return await collector.run_tracked()


# SMTP gecici hatalarinda (baglanti, 4xx) is bu kadar kez yeniden denenir.
MAIL_MAX_TRIES = 4


async def send_email(ctx: dict, to: str, subject: str, text: str) -> dict:
    import smtplib

    from arq import Retry

    from app.mail.sender import OutgoingMail, mask_email, send_mail

    try:
        status = await send_mail(OutgoingMail(to=to, subject=subject, text=text))
    except (OSError, smtplib.SMTPException) as exc:
        attempt = ctx.get("job_try", 1)
        logger.warning("mail_send_failed", to=mask_email(to), attempt=attempt, error=str(exc))
        if attempt < MAIL_MAX_TRIES and not isinstance(exc, smtplib.SMTPRecipientsRefused):
            raise Retry(defer=60 * attempt) from exc
        return {"status": "failed", "error": str(exc)[:200]}
    return {"status": status}


async def poll_telegram_updates(ctx: dict) -> dict:
    """Kullanicilarin bot'a yazdigi /start <kod> ve /stop komutlarini isler."""
    import httpx

    from app.alerts.personal import poll_telegram
    from app.core.dynamic_settings import resolve_settings

    settings = await resolve_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        return await poll_telegram(
            session_factory, settings=settings, redis=get_redis(), client=client
        )


async def send_user_digests(ctx: dict) -> dict:
    """Kullanicilarin kendi gunluk ozetleri (paper portfoy isinden sonra)."""
    import httpx

    from app.alerts.personal import send_user_digests as send_digests
    from app.core.dynamic_settings import resolve_settings

    settings = await resolve_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        return await send_digests(session_factory, settings=settings, client=client)


async def purge_auth_records(ctx: dict) -> dict:
    from app.auth.service import purge_expired

    async with session_factory() as session:
        return await purge_expired(session)


# Ayni anda tek backtest: CPU yogun; collector'lara ve sayfalara yer kalsin.
BACKTEST_LOCK_KEY = "backtest:running"
BACKTEST_LOCK_SECONDS = 30 * 60
BACKTEST_RETRY_SECONDS = 15
# Kilit bekleme dahil en fazla deneme (~1 saat sira); sonra kosu hatayla kapanir.
BACKTEST_MAX_TRIES = 240


async def run_backtest(ctx: dict, run_id: int) -> dict:
    from arq import Retry
    from sqlalchemy import update

    from app.backtest.service import execute_backtest_run
    from app.models import BacktestRun

    redis = get_redis()
    if not await redis.set(BACKTEST_LOCK_KEY, str(run_id), nx=True, ex=BACKTEST_LOCK_SECONDS):
        if ctx.get("job_try", 1) < BACKTEST_MAX_TRIES:
            raise Retry(defer=BACKTEST_RETRY_SECONDS)
        async with session_factory() as session:
            await session.execute(
                update(BacktestRun)
                .where(BacktestRun.id == run_id, BacktestRun.status == "QUEUED")
                .values(status="FAILED", error="Sıra çok uzun sürdü; koşuyu yeniden başlatın.")
            )
            await session.commit()
        return {"run_id": run_id, "status": "FAILED"}
    try:
        async with session_factory() as session:
            return await execute_backtest_run(session, run_id)
    finally:
        # Kilidi yalniz kendi aldiysa birak (zaman asimindan sonra baskasi almis olabilir).
        with contextlib.suppress(RedisError):
            if await redis.get(BACKTEST_LOCK_KEY) == str(run_id):
                await redis.delete(BACKTEST_LOCK_KEY)
