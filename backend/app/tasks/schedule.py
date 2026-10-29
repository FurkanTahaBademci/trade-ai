"""ARQ worker tanimi.

Calistirma: arq app.tasks.schedule.WorkerSettings

Collector job'lari bu dosyadaki `cron_jobs` listesinde merkezi olarak
zamanlanir. Haber ve KAP isleri ayni dakikada baslasa da haber 30 saniye
gecikmeli calisarak ani istek yukunu dagitir.
"""

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import ClassVar

import structlog
from arq import cron
from arq.connections import RedisSettings
from arq.worker import func

from app.alerts.digest import send_daily_digest
from app.alerts.service import evaluate_alerts
from app.core.config import get_settings
from app.core.redis import get_redis
from app.monitoring.service import monitor_system
from app.scheduling.service import dispatch_due_schedules
from app.tasks.jobs import (
    BACKTEST_LOCK_SECONDS,
    BACKTEST_MAX_TRIES,
    MAIL_MAX_TRIES,
    collect_analysts,
    collect_evds,
    collect_fund_flows,
    collect_fundamentals,
    collect_index_prices,
    collect_institutional_reports,
    collect_instruments,
    collect_kap,
    collect_news,
    collect_prices,
    collect_tcmb_policy,
    compute_signals,
    evaluate_sources,
    poll_telegram_updates,
    purge_auth_records,
    run_backtest,
    run_paper_portfolio,
    send_email,
    send_user_digests,
)

logger = structlog.get_logger(__name__)


HEARTBEAT_INTERVAL_SECONDS = 60


async def _write_heartbeat() -> None:
    await get_redis().set("worker:last_heartbeat", datetime.now(UTC).isoformat())


async def _heartbeat_loop() -> None:
    """Is slotlarindan bagimsiz canlilik sinyali.

    `max_jobs` sinirliyken uzun isler (fiyat, temel analiz) tum slotlari
    doldurabilir; cron `heartbeat` isi o zaman kuyrukta bekler ve izleme
    worker'i yanlislikla bayat gosterir. Bu dongu event loop'ta calisir.
    """
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        try:
            await _write_heartbeat()
        except Exception as exc:  # noqa: BLE001 - Redis kopmasi donguyu bitirmesin
            logger.warning("worker_heartbeat_failed", error=str(exc))


async def startup(ctx: dict) -> None:
    await _write_heartbeat()
    ctx["heartbeat_task"] = asyncio.create_task(_heartbeat_loop())
    logger.info("worker_started", max_jobs=WorkerSettings.max_jobs)


async def shutdown(ctx: dict) -> None:
    task = ctx.get("heartbeat_task")
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    logger.info("worker_stopped")


async def heartbeat(ctx: dict) -> None:
    """Worker'in canli oldugunu loglayan basit is (Faz 0 dogrulamasi)."""
    await get_redis().set("worker:last_heartbeat", datetime.now(UTC).isoformat())
    logger.info("worker_heartbeat")


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


class WorkerSettings:
    # ARQ renews an expiring key from its event loop; Redis PING alone cannot
    # detect a stalled worker. Keep failure detection below two minutes.
    health_check_interval = 30
    job_timeout = get_settings().worker_job_timeout
    # Ayni anda calisan is sayisi (ARQ varsayilani 10). Worker web ve API ile
    # ayni sunucuyu paylasir; cok sayida es zamanli is sayfa render'ini CPU'suz
    # birakiyordu. Isler kuyrukta sira bekler, kaybolmaz.
    max_jobs = get_settings().worker_max_jobs
    functions: ClassVar[list] = [
        collect_instruments,
        func(collect_prices, timeout=3600, name="collect_prices"),
        func(collect_index_prices, timeout=1200, name="collect_index_prices"),
        collect_kap,
        collect_news,
        func(collect_fundamentals, timeout=3600, name="collect_fundamentals"),
        collect_analysts,
        collect_fund_flows,
        collect_institutional_reports,
        evaluate_sources,
        compute_signals,
        run_paper_portfolio,
        collect_tcmb_policy,
        collect_evds,
        monitor_system,
        evaluate_alerts,
        send_daily_digest,
        send_user_digests,
        # Hesap e-postalari; kuyrukta beklemesin diye kisa zaman asimi.
        func(send_email, timeout=60, max_tries=MAIL_MAX_TRIES, name="send_email"),
        purge_auth_records,
        # Kullanici/yonetici backtest'leri; kilit beklerken Retry ile sira tutar.
        func(
            run_backtest,
            timeout=BACKTEST_LOCK_SECONDS,
            max_tries=BACKTEST_MAX_TRIES,
            name="run_backtest",
        ),
    ]
    cron_jobs: ClassVar[list] = [
        cron(heartbeat, minute=set(range(0, 60, 5))),  # her 5 dakikada bir
        cron(monitor_system, minute=set(range(1, 60, 5))),
        cron(evaluate_alerts, minute=set(range(3, 60, 10))),
        # Kullanicilarin Telegram bot'una yazdigi baglama komutlari; kisa surer.
        cron(poll_telegram_updates, minute=set(range(60)), second={10}, timeout=60),
        # Collector'larin araliklari PostgreSQL'deki collector_schedule
        # tablosundan okunur. Bu tick vadesi gelenleri Redis kuyruguna ekler.
        cron(dispatch_due_schedules, minute=set(range(60)), second={30}),
        cron(purge_auth_records, hour={4}, minute={20}),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_settings()
