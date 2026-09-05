"""ARQ cron/is fonksiyonlari.

Her fonksiyon `(ctx)` imzasi alir (ARQ konvansiyonu). Asil is mantigi
`app/collectors/*.py` icinde; burada sadece DB session acilip collector
cagriliyor. Boylece collector'lar hem CLI'dan (`scripts/run_once.py`) hem
worker'dan ayni kod yolunu kullanir.
"""

import structlog

from app.core.db import session_factory

logger = structlog.get_logger(__name__)


async def collect_instruments(ctx: dict) -> dict:
    from app.collectors.instruments import InstrumentCollector

    async with session_factory() as session:
        async with InstrumentCollector(session) as collector:
            return await collector.run_tracked()


async def collect_prices(ctx: dict) -> dict:
    from app.collectors.prices import PriceCollector

    async with session_factory() as session:
        # Cron her calistiginda tum tarihceyi degil, son birkac gunu
        # guncelliyoruz (duzeltilmis kapanislar/tatil telafisi icin 5 gun
        # payi birakildi). Ilk backfill icin scripts/run_once.py kullanilir.
        from datetime import date, timedelta

        async with PriceCollector(session, start_date=date.today() - timedelta(days=5)) as collector:
            return await collector.run_tracked()
