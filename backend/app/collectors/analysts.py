"""Kurumsal hedef fiyatlari toplar ve ticker bazli konsensus uretir."""

from __future__ import annotations

import hashlib
import re
import statistics
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector, CollectorError
from app.models import AnalystConsensus, AnalystRecommendation, Instrument, PriceDaily

ISYATIRIM_URL = (
    "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/takip-listesi.aspx?sektor=00"
)
AGGREGATOR_URL = "https://www.halkaarztakvimi.com.tr/analizler-hedef-fiyatlar/"


class _TargetTableParser(HTMLParser):
    def __init__(self, *, attribute: str, value: str) -> None:
        super().__init__(convert_charrefs=True)
        self._attribute = attribute
        self._value = value
        self._in_target = False
        self._in_cell = False
        self._row: list[str] | None = None
        self._cell_parts: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and attributes.get(self._attribute) == self._value:
            self._in_target = True
        elif self._in_target and tag == "tr":
            self._row = []
        elif self._in_target and tag in {"td", "th"} and self._row is not None:
            self._in_cell = True
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_cell and data.strip():
            self._cell_parts.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if self._in_target and tag in {"td", "th"} and self._in_cell:
            assert self._row is not None
            self._row.append(" ".join(self._cell_parts))
            self._in_cell = False
        elif self._in_target and tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
        elif self._in_target and tag == "table":
            self._in_target = False


def _turkish_decimal(value: str) -> Decimal | None:
    cleaned = value.replace("TL", "").replace("%", "").strip()
    if not cleaned or cleaned in {"-", "—"}:
        return None
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise CollectorError(f"Gecersiz Turkce sayi: {value!r}") from exc


def _turkish_date(value: str) -> date:
    try:
        day, month, year = (int(part) for part in value.split("."))
        return date(year, month, day)
    except (TypeError, ValueError) as exc:
        raise CollectorError(f"Gecersiz Turkce tarih: {value!r}") from exc


def normalize_recommendation(value: str) -> str:
    normalized = value.upper().translate(str.maketrans("ÇĞİÖŞÜ", "CGIOSU"))
    normalized = re.sub(r"\s+", " ", normalized).strip(" .")
    if normalized in {
        "AL",
        "GUCLU AL",
        "END. USTU",
        "ENDEKS USTU GETIRI",
        "ENDEKS UZERI GETIRI",
        "EU",
        "OUTPERFORM",
        "OVERWEIGHT",
        "BUY",
    }:
        return "BUY"
    if normalized in {
        "TUT",
        "NOTR",
        "ENDEKSE PARALEL GETIRI",
        "EP",
        "MARKET PERFORM",
        "NEUTRAL",
        "EQUAL WEIGHT",
        "HOLD",
    }:
        return "HOLD"
    if normalized in {
        "SAT",
        "END. ALTI",
        "ENDEKS ALTI GETIRI",
        "EA",
        "UNDERPERFORM",
        "UNDERWEIGHT",
        "SELL",
    }:
        return "SELL"
    return "REVIEW"


def _source_key(fields: dict[str, Any]) -> str:
    identity = "|".join(
        str(fields.get(key) or "")
        for key in (
            "source",
            "ticker",
            "institution",
            "recommendation_date",
            "recommendation_raw",
            "target_price",
        )
    )
    return hashlib.sha256(identity.encode()).hexdigest()


def parse_isyatirim_recommendations(html: str) -> list[dict]:
    parser = _TargetTableParser(attribute="data-csvname", value="takipozet")
    parser.feed(html)
    rows: list[dict] = []
    for cells in parser.rows:
        if len(cells) < 7 or cells[0] == "Kod":
            continue
        recommendation_date = _turkish_date(cells[4])
        target = _turkish_decimal(cells[2])
        reference = _turkish_decimal(cells[5])
        fields = {
            "ticker": cells[0].split()[0].upper(),
            "source": "isyatirim",
            "institution": "İş Yatırım",
            "recommendation_raw": cells[1],
            "recommendation_normalized": normalize_recommendation(cells[1]),
            "target_price": target,
            "reference_price": reference,
            "upside_pct": _turkish_decimal(cells[3]),
            "recommendation_date": recommendation_date,
            "source_url": ISYATIRIM_URL,
            "raw_data": {"cells": cells},
        }
        fields["source_key"] = _source_key(fields)
        rows.append(fields)
    if not rows:
        raise CollectorError("Is Yatirim takip tablosunda satir bulunamadi")
    return rows


def parse_aggregator_recommendations(html: str) -> list[dict]:
    parser = _TargetTableParser(attribute="id", value="hedef-table")
    parser.feed(html)
    rows: list[dict] = []
    for cells in parser.rows:
        if len(cells) < 5 or cells[0] == "Bist Kodu":
            continue
        recommendation_date = _turkish_date(cells[2])
        fields = {
            "ticker": cells[0].split()[0].upper(),
            "source": "halkaarztakvimi",
            "institution": cells[1],
            "recommendation_raw": cells[3],
            "recommendation_normalized": normalize_recommendation(cells[3]),
            "target_price": _turkish_decimal(cells[4]),
            "reference_price": None,
            "upside_pct": None,
            "recommendation_date": recommendation_date,
            "source_url": AGGREGATOR_URL,
            "raw_data": {"cells": cells},
        }
        fields["source_key"] = _source_key(fields)
        rows.append(fields)
    if not rows:
        raise CollectorError("Hedef fiyat agregator tablosunda satir bulunamadi")
    return rows


# Hedef fiyatlar fiyat dustukce "potansiyel" uretir; eski tavsiye bu yuzden
# hem agirlik kaybeder hem belli bir yastan sonra tamamen dusulur.
ANALYST_MAX_AGE_DAYS = 180
ANALYST_HALF_LIFE_DAYS = 90


def recommendation_weight(age_days: int) -> Decimal:
    return Decimal(str(0.5 ** (max(0, age_days) / ANALYST_HALF_LIFE_DAYS)))


def calculate_consensus(
    recommendations: list[AnalystRecommendation | dict[str, Any]],
    *,
    market_prices: dict[str, Decimal],
    as_of_date: date,
) -> list[dict]:
    latest: dict[tuple[str, str], AnalystRecommendation | dict[str, Any]] = {}

    def get(row, key):
        return row.get(key) if isinstance(row, dict) else getattr(row, key)

    def age(row) -> int:
        return (as_of_date - get(row, "recommendation_date")).days

    for row in recommendations:
        if not 0 <= age(row) <= ANALYST_MAX_AGE_DAYS:
            continue
        key = (get(row, "ticker"), get(row, "institution").casefold())
        previous = latest.get(key)
        row_rank = (get(row, "recommendation_date"), get(row, "source") == "isyatirim")
        previous_rank = (
            (get(previous, "recommendation_date"), get(previous, "source") == "isyatirim")
            if previous is not None
            else None
        )
        if previous_rank is None or row_rank > previous_rank:
            latest[key] = row

    grouped: dict[str, list] = defaultdict(list)
    for row in latest.values():
        grouped[get(row, "ticker")].append(row)

    output: list[dict] = []
    vote_values = {"BUY": Decimal(100), "HOLD": Decimal(50), "SELL": Decimal(0)}
    for ticker, rows in sorted(grouped.items()):
        counts = Counter(get(row, "recommendation_normalized") for row in rows)
        weights = {id(row): recommendation_weight(age(row)) for row in rows}
        targeted = [row for row in rows if get(row, "target_price")]
        targets = [get(row, "target_price") for row in targeted]
        voted = [row for row in rows if get(row, "recommendation_normalized") in vote_values]
        average = _weighted_mean(
            [(get(row, "target_price"), weights[id(row)]) for row in targeted]
        )
        recommendation_score = _weighted_mean(
            [(vote_values[get(row, "recommendation_normalized")], weights[id(row)]) for row in voted]
        )
        median = Decimal(str(statistics.median(targets))) if targets else None
        dispersion = None
        if average and len(targets) >= 2:
            dispersion = Decimal(str(statistics.pstdev(targets))) / average
        market_price = market_prices.get(ticker)
        implied_upside = ((average / market_price) - 1) * 100 if average and market_price else None
        source_counts = Counter(get(row, "source") for row in rows)
        output.append(
            {
                "ticker": ticker,
                "as_of_date": as_of_date,
                "institution_count": len(rows),
                "buy_count": counts["BUY"],
                "hold_count": counts["HOLD"],
                "sell_count": counts["SELL"],
                "review_count": counts["REVIEW"],
                "average_target": average,
                "median_target": median,
                "minimum_target": min(targets) if targets else None,
                "maximum_target": max(targets) if targets else None,
                "market_price": market_price,
                "implied_upside_pct": implied_upside,
                "target_dispersion": dispersion,
                "recommendation_score": recommendation_score,
                "average_age_days": Decimal(sum(age(row) for row in rows)) / len(rows),
                "source_breakdown": dict(source_counts),
            }
        )
    return output


def _weighted_mean(pairs: list[tuple[Decimal, Decimal]]) -> Decimal | None:
    total = sum((weight for _, weight in pairs), Decimal(0))
    if not pairs or total <= 0:
        return None
    return sum((value * weight for value, weight in pairs), Decimal(0)) / total


async def recompute_analyst_consensus(session: AsyncSession) -> list[dict]:
    """Tum kaynaklardan (isyatirim, halkaarztakvimi, kurum PDF hatti, ...)
    biriken `analyst_recommendation` satirlarindan ticker bazli konsensusu
    yeniden hesaplar. Her kaynak collector'i kendi upsert'inden sonra bunu
    cagirir; boylece konsensus hangi kaynagin son calistigina bakmadan
    guncel kalir.
    """
    cutoff = datetime.now(UTC).date() - timedelta(days=365)
    recommendations = list(
        (
            await session.scalars(
                select(AnalystRecommendation).where(
                    AnalystRecommendation.recommendation_date >= cutoff
                )
            )
        ).all()
    )
    price_rows = (
        await session.execute(
            select(PriceDaily.ticker, PriceDaily.close)
            .distinct(PriceDaily.ticker)
            .order_by(PriceDaily.ticker, PriceDaily.date.desc())
        )
    ).all()
    as_of = datetime.now(ZoneInfo("Europe/Istanbul")).date()
    consensus = calculate_consensus(
        recommendations,
        market_prices=dict(price_rows),
        as_of_date=as_of,
    )
    if consensus:
        stmt = pg_insert(AnalystConsensus).values(consensus)
        update_fields = {
            key: getattr(stmt.excluded, key)
            for key in consensus[0]
            if key not in {"ticker", "as_of_date"}
        }
        update_fields["computed_at"] = func.now()
        update_fields["updated_at"] = func.now()
        await session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_analyst_consensus_identity", set_=update_fields
            )
        )
        await session.commit()
    return consensus


class AnalystCollector(BaseCollector):
    name = "analysts"

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(rate_limit_per_sec=1.0)
        self._session = session

    async def run(self) -> dict:
        source_results: dict[str, list[dict]] = {}
        failures: dict[str, str] = {}
        sources = {
            "isyatirim": (ISYATIRIM_URL, parse_isyatirim_recommendations),
            "halkaarztakvimi": (AGGREGATOR_URL, parse_aggregator_recommendations),
        }
        for source, (url, parser) in sources.items():
            try:
                html = (await self.get_bytes(url)).decode("utf-8")
                source_results[source] = parser(html)
            except Exception as exc:  # noqa: BLE001 - bir kaynak digerini durdurmasin
                failures[source] = str(exc)
                self.log.error("analyst_source_failed", source=source, error=str(exc))
        if not source_results:
            raise CollectorError(f"Tum analist kaynaklari basarisiz: {failures}")

        active_tickers = set(
            (
                await self._session.scalars(
                    select(Instrument.ticker).where(Instrument.is_active.is_(True))
                )
            ).all()
        )
        mapped = [
            row
            for rows in source_results.values()
            for row in rows
            if row["ticker"] in active_tickers
        ]
        existing = set(
            (
                await self._session.scalars(
                    select(AnalystRecommendation.source_key).where(
                        AnalystRecommendation.source_key.in_([row["source_key"] for row in mapped])
                    )
                )
            ).all()
        )
        if mapped:
            stmt = pg_insert(AnalystRecommendation).values(mapped)
            await self._session.execute(
                stmt.on_conflict_do_update(
                    constraint="uq_analyst_recommendation_source_key",
                    set_={
                        "recommendation_raw": stmt.excluded.recommendation_raw,
                        "recommendation_normalized": stmt.excluded.recommendation_normalized,
                        "target_price": stmt.excluded.target_price,
                        "reference_price": stmt.excluded.reference_price,
                        "upside_pct": stmt.excluded.upside_pct,
                        "raw_data": stmt.excluded.raw_data,
                        "fetched_at": func.now(),
                        "updated_at": func.now(),
                    },
                )
            )
            await self._session.commit()

        consensus = await recompute_analyst_consensus(self._session)
        return {
            "sources_ok": len(source_results),
            "source_failures": failures,
            "listed": sum(len(rows) for rows in source_results.values()),
            "accepted": len(mapped),
            "new": len({row["source_key"] for row in mapped} - existing),
            "consensus": len(consensus),
        }
