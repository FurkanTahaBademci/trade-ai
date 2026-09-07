"""ARQ cron/is fonksiyonlari.

Her fonksiyon `(ctx)` imzasi alir (ARQ konvansiyonu). Asil is mantigi
`app/collectors/*.py` icinde; burada sadece DB session acilip collector
cagriliyor. Boylece collector'lar hem CLI'dan (`scripts/run_once.py`) hem
worker'dan ayni kod yolunu kullanir.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import structlog

from app.core.db import session_factory

logger = structlog.get_logger(__name__)


async def collect_instruments(ctx: dict) -> dict:
    from app.collectors.instruments import InstrumentCollector

    async with session_factory() as session, InstrumentCollector(session) as collector:
        return await collector.run_tracked()


async def collect_prices(ctx: dict) -> dict:
    from app.collectors.prices import PriceCollector

    # Cron her calistiginda tum tarihceyi degil, son birkac gunu
    # guncelliyoruz (duzeltilmis kapanislar/tatil telafisi icin 5 gun
    # payi birakildi). Ilk backfill icin scripts/run_once.py kullanilir.
    async with (
        session_factory() as session,
        PriceCollector(
            session,
            start_date=datetime.now(ZoneInfo("Europe/Istanbul")).date() - timedelta(days=5),
        ) as collector,
    ):
        return await collector.run_tracked()


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
