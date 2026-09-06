"""Bir collector'i tek seferlik elle calistirmak icin CLI.

Kullanim:
    python -m scripts.run_once instruments
    python -m scripts.run_once kap --days 3
    python -m scripts.run_once kap --days 30 --no-attachments
    python -m scripts.run_once news
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


COLLECTORS = {
    "instruments": lambda args: run_instruments(),
    "kap": lambda args: run_kap(args.days, not args.no_attachments),
    "news": lambda args: run_news(),
    "prices": lambda args: run_prices(
        tickers=args.tickers.split(",") if args.tickers else None,
        days=args.days,
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
    args = parser.parse_args()

    result = asyncio.run(COLLECTORS[args.collector](args))
    print(f"\n=== {args.collector} sonucu ===")
    for key, value in result.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
