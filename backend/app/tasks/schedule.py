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
from app.tasks.jobs import (
    collect_analysts,
    collect_fund_flows,
    collect_fundamentals,
    collect_institutional_reports,
    collect_instruments,
    collect_kap,
    collect_news,
    collect_prices,
    compute_signals,
    evaluate_sources,
)

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
    functions: ClassVar[list] = [
        collect_instruments,
        collect_prices,
        collect_kap,
        collect_news,
        collect_fundamentals,
        collect_analysts,
        collect_fund_flows,
        collect_institutional_reports,
        evaluate_sources,
        compute_signals,
    ]
    cron_jobs: ClassVar[list] = [
        cron(heartbeat, minute=set(range(0, 60, 5))),  # her 5 dakikada bir
        cron(collect_kap, minute=set(range(0, 60, 5))),
        cron(collect_news, minute=set(range(0, 60, 5)), second=30),
        # Haber/KAP toplandiktan sonra; LLM_ENABLED=false ise ucretli cagri yok.
        cron(evaluate_sources, minute=set(range(2, 60, 10))),
        # LLM degerlendirmesinden sonra bilesik skorlari tazele.
        cron(compute_signals, minute=set(range(4, 60, 10))),
        # Aday evren temel analizi; gunde bir, instrument yenilemesinden sonra.
        cron(collect_fundamentals, hour={7}, minute={0}),
        # Kurumsal hedefler sabah; TEFAS akimi gun sonu verisi sonrasinda.
        cron(collect_analysts, hour={7}, minute={30}),
        # Kurum PDF hatti (PhillipCapital) analist collector'indan sonra;
        # kendi upsert'inin ardindan konsensusu tekrar hesaplar.
        cron(collect_institutional_reports, hour={7}, minute={45}),
        cron(collect_fund_flows, hour={20}, minute={0}),
        # Hisse evreni gunde bir kere yeterli (KAP uyelik degisimi nadir).
        cron(collect_instruments, hour={6}, minute={0}),
        # Fiyat: BIST kapanisi (18:00-18:10 TRT) sonrasi guncel veri icin 18:30.
        cron(collect_prices, hour={18}, minute={30}),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_settings()
