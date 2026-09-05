"""ARQ worker tanimi.

Calistirma: arq app.tasks.schedule.WorkerSettings

Faz 2+'da collector job'lari (kap_poll, news_poll, ...) buraya `cron_jobs`
listesine eklenecek. Faz 0'da sadece worker'in ayakta oldugunu ve Redis'e
baglandigini dogrulayan bir ping job'u var.
"""

import structlog
from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


async def startup(ctx: dict) -> None:
    logger.info("worker_started")


async def shutdown(ctx: dict) -> None:
    logger.info("worker_stopped")


async def heartbeat(ctx: dict) -> None:
    """Worker'in canli oldugunu loglayan basit is (Faz 0 dogrulamasi)."""
    logger.info("worker_heartbeat")


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


class WorkerSettings:
    functions: list = []
    cron_jobs = [
        cron(heartbeat, minute=set(range(0, 60, 5))),  # her 5 dakikada bir
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_settings()
