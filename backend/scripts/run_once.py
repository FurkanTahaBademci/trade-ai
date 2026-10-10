"""Bir collector'i tek seferlik elle calistirmak icin CLI.

Kullanim:
    python -m scripts.run_once instruments
    python -m scripts.run_once kap --days 3
    python -m scripts.run_once news
    python -m scripts.run_once llm
    python -m scripts.run_once fundamentals --tickers THYAO,ASELS --start-year 2025
    python -m scripts.run_once analysts
    python -m scripts.run_once institutional-reports
    python -m scripts.run_once institutional-reports --max-pages 2
    python -m scripts.run_once fund-flows --fund-kind YAT --days 7
    python -m scripts.run_once signals --tickers THYAO,ASELS
    python -m scripts.run_once signals --days 120          # her islem gunu icin geriye donuk
    python -m scripts.run_once paper
    python -m scripts.run_once kap-event-dates             # takvim olay tarihlerini doldur
    python -m scripts.run_once tcmb-policy --years 2025,2026
    python -m scripts.run_once evds                         # EVDS_API_KEY gerekir
    python -m scripts.run_once evds --save-fixture          # gercek yaniti fixture'a yaz
    python -m scripts.run_once prices --tickers THYAO,ASELS,GARAN --days 30
    python -m scripts.run_once prices                    # tum aktif hisseler, 3 yil backfill
    python -m scripts.run_once index-prices --days 30
    python -m scripts.run_once index-prices               # XU100, 3 yil backfill

Idempotency dogrulamasi (plan Bolum 7):
    python -m scripts.run_once instruments   # 1. calistirma
    python -m scripts.run_once instruments   # 2. calistirma -> ayni sonuc, kopya satir yok
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import structlog

from app.core.db import session_factory
from app.core.logging import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)


async def run_instruments() -> dict:
    from app.collectors.instruments import InstrumentCollector

    async with session_factory() as session, InstrumentCollector(session) as collector:
        return await collector.run_tracked()


async def run_prices(tickers: list[str] | None, days: int | None, chunk_size: int | None = None) -> dict:
    from app.collectors.prices import PriceCollector

    start_date = (
        datetime.now(ZoneInfo("Europe/Istanbul")).date() - timedelta(days=days) if days else None
    )

    async with (
        session_factory() as session,
        PriceCollector(session, tickers=tickers, start_date=start_date, chunk_size=chunk_size) as collector,
    ):
        return await collector.run_tracked()


async def run_index_prices(days: int | None) -> dict:
    from app.collectors.index_prices import IndexPriceCollector

    start_date = (
        datetime.now(ZoneInfo("Europe/Istanbul")).date() - timedelta(days=days) if days else None
    )

    async with (
        session_factory() as session,
        IndexPriceCollector(session, start_date=start_date) as collector,
    ):
        return await collector.run_tracked()


async def run_kap(days: int | None) -> dict:
    from app.collectors.kap import DEFAULT_LOOKBACK_DAYS, KapCollector

    async with (
        session_factory() as session,
        KapCollector(
            session,
            lookback_days=days or DEFAULT_LOOKBACK_DAYS,
        ) as collector,
    ):
        return await collector.run_tracked()


async def run_news() -> dict:
    from app.collectors.news import NewsCollector

    async with session_factory() as session, NewsCollector(session) as collector:
        return await collector.run_tracked()


async def run_llm() -> dict:
    from app.llm.service import run_llm_evaluations

    async with session_factory() as session:
        return await run_llm_evaluations(session)


async def run_fundamentals(
    tickers: list[str] | None, start_year: int | None, end_year: int | None
) -> dict:
    from app.collectors.fundamentals import FundamentalsCollector

    current_year = datetime.now(ZoneInfo("Europe/Istanbul")).year
    start = start_year or current_year - 1
    end = end_year or current_year
    if end < start:
        raise ValueError("--end-year, --start-year degerinden kucuk olamaz")
    async with (
        session_factory() as session,
        FundamentalsCollector(
            session,
            tickers=tickers,
            years=list(range(start, end + 1)),
        ) as collector,
    ):
        return await collector.run_tracked()


async def run_analysts() -> dict:
    from app.collectors.analysts import AnalystCollector

    async with session_factory() as session, AnalystCollector(session) as collector:
        return await collector.run_tracked()


async def run_institutional_reports(max_pages: int | None) -> dict:
    from app.collectors.institutional_reports import InstitutionalReportCollector

    async with (
        session_factory() as session,
        InstitutionalReportCollector(session, max_pages=max_pages) as collector,
    ):
        return await collector.run_tracked()


async def run_fund_flows(fund_kind: str, days: int | None) -> dict:
    from app.collectors.fund_flows import FundFlowCollector

    lookback = days or 7
    if lookback < 1 or lookback > 28:
        raise ValueError("fund-flows --days 1 ile 28 arasinda olmali")
    end = datetime.now(ZoneInfo("Europe/Istanbul")).date()
    start = end - timedelta(days=lookback - 1)
    async with (
        session_factory() as session,
        FundFlowCollector(
            session, fund_kind=fund_kind, start_date=start, end_date=end
        ) as collector,
    ):
        return await collector.run_tracked()


async def run_signals(tickers: list[str] | None, days: int | None = None) -> dict:
    from sqlalchemy import select

    from app.models import IndexDaily
    from app.signals.service import run_signal_engine

    if not days:
        async with session_factory() as session:
            return await run_signal_engine(session, tickers=tickers)

    # Geriye donuk doldurma: her islem gunu o gun bilinen veriyle hesaplanir.
    start = datetime.now(ZoneInfo("Europe/Istanbul")).date() - timedelta(days=days)
    async with session_factory() as session:
        trading_days = list(
            (
                await session.scalars(
                    select(IndexDaily.date)
                    .where(IndexDaily.index_code == "XU100", IndexDaily.date >= start)
                    .order_by(IndexDaily.date)
                )
            ).all()
        )
    totals = {"days": len(trading_days), "snapshots": 0, "new": 0, "updated": 0}
    for day in trading_days:
        async with session_factory() as session:
            result = await run_signal_engine(session, tickers=tickers, as_of_date=day)
        for key in ("snapshots", "new", "updated"):
            totals[key] += result[key]
        logger.info("signals_backfill_day", **result)
    return totals


async def run_kap_event_dates() -> dict:
    """Govdesi olan eski KAP bildirimlerinden olay tarihini (yeniden) cikarir."""
    from sqlalchemy import or_, select, update

    from app.market_calendar.classifier import KAP_PREFILTER_STEMS
    from app.market_calendar.event_dates import disclosure_event_date
    from app.models import KapDisclosure

    patterns = [f"%{stem}%" for stem in KAP_PREFILTER_STEMS]
    scanned = updated = 0
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(
                    KapDisclosure.disclosure_index,
                    KapDisclosure.kap_title,
                    KapDisclosure.subject,
                    KapDisclosure.disclosure_class,
                    KapDisclosure.body_text,
                    KapDisclosure.event_date,
                ).where(
                    KapDisclosure.body_text.is_not(None),
                    or_(
                        *[KapDisclosure.kap_title.ilike(p) for p in patterns],
                        *[KapDisclosure.subject.ilike(p) for p in patterns],
                    ),
                )
            )
        ).all()
        for row in rows:
            scanned += 1
            event = disclosure_event_date(
                title=row.kap_title,
                subject=row.subject,
                disclosure_class=row.disclosure_class,
                body_text=row.body_text,
            )
            new_date = event.event_date if event else None
            if new_date == row.event_date:
                continue
            await session.execute(
                update(KapDisclosure)
                .where(KapDisclosure.disclosure_index == row.disclosure_index)
                .values(event_date=new_date, event_detail=event.detail if event else None)
            )
            updated += 1
        await session.commit()
    return {"scanned": scanned, "updated": updated}


async def run_evds(save_fixture: bool) -> dict:
    from pathlib import Path

    from app.collectors.evds import EvdsCollector
    from app.collectors.evds import save_fixture as write_fixture

    async with session_factory() as session, EvdsCollector(session) as collector:
        if save_fixture:
            path = Path("tests/fixtures/evds/series_sample.json")
            write_fixture(await collector.fetch_raw(), path)
            return {"fixture": str(path)}
        return await collector.run_tracked()


async def run_paper() -> dict:
    from app.paper.service import run_paper_portfolio

    async with session_factory() as session:
        return await run_paper_portfolio(session)


async def run_tcmb_policy(years: list[int] | None, refresh: bool) -> dict:
    from app.collectors.tcmb_policy import TcmbPolicyCollector

    async with (
        session_factory() as session,
        TcmbPolicyCollector(session, years=years, refresh=refresh) as collector,
    ):
        return await collector.run_tracked()


COLLECTORS = {
    "evds": lambda args: run_evds(args.save_fixture),
    "kap-event-dates": lambda args: run_kap_event_dates(),
    "analysts": lambda args: run_analysts(),
    "institutional-reports": lambda args: run_institutional_reports(args.max_pages),
    "fund-flows": lambda args: run_fund_flows(args.fund_kind, args.days),
    "fundamentals": lambda args: run_fundamentals(
        tickers=args.tickers.split(",") if args.tickers else None,
        start_year=args.start_year,
        end_year=args.end_year,
    ),
    "index-prices": lambda args: run_index_prices(args.days),
    "instruments": lambda args: run_instruments(),
    "kap": lambda args: run_kap(args.days),
    "llm": lambda args: run_llm(),
    "news": lambda args: run_news(),
    "paper": lambda args: run_paper(),
    "prices": lambda args: run_prices(
        tickers=args.tickers.split(",") if args.tickers else None,
        days=args.days,
        chunk_size=args.chunk_size,
    ),
    "signals": lambda args: run_signals(
        args.tickers.split(",") if args.tickers else None, args.days
    ),
    "tcmb-policy": lambda args: run_tcmb_policy(
        [int(year) for year in args.years.split(",")] if args.years else None,
        args.refresh,
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("collector", choices=sorted(COLLECTORS.keys()))
    parser.add_argument(
        "--tickers",
        help="Virgulle ayrilmis ticker listesi (orn. THYAO,ASELS). Verilmezse tum aktif hisseler.",
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Kac gun geriye gidilecek (kap: 3 gun, prices: 3 yil varsayilan).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        help="Fiyat toplayici chunk boyutu (varsayilan: 10).",
    )
    parser.add_argument("--start-year", type=int, help="Finansal tablo baslangic yili.")
    parser.add_argument("--end-year", type=int, help="Finansal tablo bitis yili.")
    parser.add_argument("--years", help="TCMB icin virgulle ayrilmis yil listesi.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="TCMB tarafinda daha once yayimlanmis karar metinlerini yeniden isle.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="institutional-reports: liste sayfasi taramasini N sayfayla sinirla (test icin).",
    )
    parser.add_argument(
        "--fund-kind",
        choices=["YAT", "EMK", "BYF", "GYF", "GSYF"],
        default="YAT",
        help="TEFAS fon tipi (varsayilan: YAT).",
    )
    parser.add_argument(
        "--save-fixture",
        action="store_true",
        help="evds: gercek yaniti tests/fixtures/evds/series_sample.json'a yaz.",
    )
    args = parser.parse_args()

    result = asyncio.run(COLLECTORS[args.collector](args))
    print(f"\n=== {args.collector} sonucu ===")
    for key, value in result.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
