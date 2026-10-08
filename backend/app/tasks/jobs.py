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


async def collect_index_prices(ctx: dict) -> dict:
    from app.collectors.index_prices import IndexPriceCollector

    # prices.py ile ayni desen: cron her calistiginda tum tarihceyi degil,
    # son birkac gunu gunceller (duzeltilmis kapanislar icin pay birakildi).
    async with (
        session_factory() as session,
        IndexPriceCollector(
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
    from app.signals.service import run_signal_engine

    async with session_factory() as session:
        return await run_signal_engine(session)


async def run_paper_portfolio(ctx: dict) -> dict:
    from app.paper.service import run_paper_portfolio as execute_paper_portfolio

    async with session_factory() as session:
        return await execute_paper_portfolio(session)


async def collect_tcmb_policy(ctx: dict) -> dict:
    from app.collectors.tcmb_policy import TcmbPolicyCollector

    async with session_factory() as session, TcmbPolicyCollector(session) as collector:
        return await collector.run_tracked()
