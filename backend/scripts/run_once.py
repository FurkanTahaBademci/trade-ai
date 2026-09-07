"""Bir collector'i tek seferlik elle calistirmak icin CLI.

Kullanim:
    python -m scripts.run_once instruments
    python -m scripts.run_once kap --days 3
    python -m scripts.run_once kap --days 30 --no-attachments
    python -m scripts.run_once news
    python -m scripts.run_once llm
    python -m scripts.run_once fundamentals --tickers THYAO,ASELS --start-year 2025
    python -m scripts.run_once analysts
    python -m scripts.run_once institutional-reports
    python -m scripts.run_once institutional-reports --max-pages 2
    python -m scripts.run_once fund-flows --fund-kind YAT --days 7
    python -m scripts.run_once signals --tickers THYAO,ASELS
    python -m scripts.run_once paper
    python -m scripts.run_once tcmb-policy --years 2025,2026
    python -m scripts.run_once prices --tickers THYAO,ASELS,GARAN --days 30
    python -m scripts.run_once prices                    # tum aktif hisseler, 3 yil backfill

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


async def run_prices(tickers: list[str] | None, days: int | None) -> dict:
    from app.collectors.prices import PriceCollector

    start_date = (
        datetime.now(ZoneInfo("Europe/Istanbul")).date() - timedelta(days=days) if days else None
    )

    async with (
        session_factory() as session,
        PriceCollector(session, tickers=tickers, start_date=start_date) as collector,
    ):
        return await collector.run_tracked()


async def run_kap(days: int | None, download_attachments: bool) -> dict:
    from app.collectors.kap import DEFAULT_LOOKBACK_DAYS, KapCollector

    async with (
        session_factory() as session,
        KapCollector(
            session,
            lookback_days=days or DEFAULT_LOOKBACK_DAYS,
            download_attachments=download_attachments,
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


async def run_signals(tickers: list[str] | None) -> dict:
    from app.signals.service import run_signal_engine

    async with session_factory() as session:
        return await run_signal_engine(session, tickers=tickers)


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
    "analysts": lambda args: run_analysts(),
    "institutional-reports": lambda args: run_institutional_reports(args.max_pages),
    "fund-flows": lambda args: run_fund_flows(args.fund_kind, args.days),
    "fundamentals": lambda args: run_fundamentals(
        tickers=args.tickers.split(",") if args.tickers else None,
        start_year=args.start_year,
        end_year=args.end_year,
    ),
    "instruments": lambda args: run_instruments(),
    "kap": lambda args: run_kap(args.days, not args.no_attachments),
    "llm": lambda args: run_llm(),
    "news": lambda args: run_news(),
    "paper": lambda args: run_paper(),
    "prices": lambda args: run_prices(
        tickers=args.tickers.split(",") if args.tickers else None,
        days=args.days,
    ),
    "signals": lambda args: run_signals(args.tickers.split(",") if args.tickers else None),
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
        "--no-attachments",
        action="store_true",
        help="KAP eklerini indirme; yalnizca bildirim ve ek metadatasini kaydet.",
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
    args = parser.parse_args()

    result = asyncio.run(COLLECTORS[args.collector](args))
    print(f"\n=== {args.collector} sonucu ===")
    for key, value in result.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
