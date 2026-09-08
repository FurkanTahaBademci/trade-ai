"""ARQ worker tanimi.

Calistirma: arq app.tasks.schedule.WorkerSettings

Collector job'lari bu dosyadaki `cron_jobs` listesinde merkezi olarak
zamanlanir. Haber ve KAP isleri ayni dakikada baslasa da haber 30 saniye
gecikmeli calisarak ani istek yukunu dagitir.
"""

from datetime import UTC, datetime
from typing import ClassVar

import structlog
from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.redis import get_redis
from app.monitoring.service import monitor_system
from app.scheduling.service import dispatch_due_schedules
from app.tasks.jobs import (
    collect_analysts,
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
    run_paper_portfolio,
)

logger = structlog.get_logger(__name__)


async def startup(ctx: dict) -> None:
    await get_redis().set("worker:last_heartbeat", datetime.now(UTC).isoformat())
    logger.info("worker_started")


async def shutdown(ctx: dict) -> None:
    logger.info("worker_stopped")


async def heartbeat(ctx: dict) -> None:
    """Worker'in canli oldugunu loglayan basit is (Faz 0 dogrulamasi)."""
    await get_redis().set("worker:last_heartbeat", datetime.now(UTC).isoformat())
    logger.info("worker_heartbeat")


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


class WorkerSettings:
    functions: ClassVar[list] = [
        collect_instruments,
        collect_prices,
        collect_index_prices,
        collect_kap,
        collect_news,
        collect_fundamentals,
        collect_analysts,
        collect_fund_flows,
        collect_institutional_reports,
        evaluate_sources,
        compute_signals,
        run_paper_portfolio,
        collect_tcmb_policy,
        monitor_system,
    ]
    cron_jobs: ClassVar[list] = [
        cron(heartbeat, minute=set(range(0, 60, 5))),  # her 5 dakikada bir
        cron(monitor_system, minute=set(range(1, 60, 5))),
        # Collector'larin araliklari PostgreSQL'deki collector_schedule
        # tablosundan okunur. Bu tick vadesi gelenleri Redis kuyruguna ekler.
        cron(dispatch_due_schedules, minute=set(range(60)), second={30}),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_settings()
