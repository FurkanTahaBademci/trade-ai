"""ARQ worker tanimi.

Calistirma: arq app.tasks.schedule.WorkerSettings

Collector job'lari bu dosyadaki `cron_jobs` listesinde merkezi olarak
zamanlanir. Haber ve KAP isleri ayni dakikada baslasa da haber 30 saniye
gecikmeli calisarak ani istek yukunu dagitir.
"""

from typing import ClassVar

import structlog
from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.tasks.jobs import collect_instruments, collect_kap, collect_news, collect_prices

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
    functions: ClassVar[list] = [collect_instruments, collect_prices, collect_kap, collect_news]
    cron_jobs: ClassVar[list] = [
        cron(heartbeat, minute=set(range(0, 60, 5))),  # her 5 dakikada bir
        cron(collect_kap, minute=set(range(0, 60, 5))),
        cron(collect_news, minute=set(range(0, 60, 5)), second=30),
        # Hisse evreni gunde bir kere yeterli (KAP uyelik degisimi nadir).
        cron(collect_instruments, hour={6}, minute={0}),
        # Fiyat: BIST kapanisi (18:00-18:10 TRT) sonrasi guncel veri icin 18:30.
        cron(collect_prices, hour={18}, minute={30}),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_settings()
