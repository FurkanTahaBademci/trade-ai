"""Is Yatirim finansal tablo collector'i ve temel oran motoru."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector, CollectorError
from app.models import FinancialFact, FundamentalSnapshot, Instrument, LlmEvaluation

FINANCIALS_URL = (
    "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/MaliTablo"
)
FINANCIAL_GROUPS = ("XI_29", "UFRS", "UFRS_K")
PERIODS = (3, 6, 9, 12)

ITEM_CODES = {
    "current_assets": "1A",
    "cash": "1AA",
    "current_liabilities": "2A",
    "short_term_debt": "2AA",
    "long_term_debt": "2BA",
    "equity": "2N",
    "revenue": "3C",
    "gross_profit": "3D",
    "operating_profit": "3H",
    "net_income": "3Z",
    "depreciation": "4B",
    "operating_cash_flow": "4C",
    "free_cash_flow": "4CB",
}


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    raw = str(value).strip().replace(",", "")
    if not raw or raw == "-":
        return None
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise CollectorError(f"Finansal deger sayi degil: {value!r}") from exc


def map_financial_response(
    ticker: str,
    financial_group: str,
    year: int,
    payload: dict | list,
    *,
    exchange: str = "TRY",
) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
        raise CollectorError("Is Yatirim mali tablo yaniti value listesi icermiyor")
    if payload.get("ok") is False:
        raise CollectorError(
            f"Is Yatirim mali tablo hatasi: {payload.get('errorCode')} "
            f"{payload.get('errorDescription')}"
        )

    mapped: list[dict] = []
    for row in payload["value"]:
        if not isinstance(row, dict):
            continue
        item_code = str(row.get("itemCode") or "").strip()
        item_name_tr = str(row.get("itemDescTr") or "").strip()
        if not item_code or not item_name_tr:
            continue
        for slot, period in enumerate(PERIODS, start=1):
            raw_value = row.get(f"value{slot}")
            value = _decimal(raw_value)
            if value is None:
                continue
            mapped.append(
                {
                    "ticker": ticker.upper(),
                    "financial_group": financial_group,
                    "exchange": exchange.upper(),
                    "year": year,
                    "period": period,
                    "item_code": item_code,
                    "item_name_tr": item_name_tr,
                    "item_name_en": str(row.get("itemDescEng") or "").strip() or None,
                    "value": value,
                    "raw_value": str(raw_value),
                }
            )
    return mapped


def _safe_div(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _year_over_year(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    if current is None or previous in (None, 0):
        return None
    if previous > 0:
        return (current / previous) - 1
    if current >= 0:
        return Decimal(1)
    return (abs(previous) - abs(current)) / abs(previous)


def _linear_score(
    value: Decimal | None, low: str, high: str, *, inverse: bool = False
) -> float | None:
    if value is None:
        return None
    low_value, high_value = Decimal(low), Decimal(high)
    score = float((value - low_value) / (high_value - low_value) * 100)
    score = max(0.0, min(100.0, score))
    return 100.0 - score if inverse else score


def _average(values: list[float | None]) -> float | None:
    available = [value for value in values if value is not None]
    return sum(available) / len(available) if available else None


def calculate_fundamental_snapshot(
    *,
    ticker: str,
    financial_group: str,
    exchange: str,
    year: int,
    period: int,
    current: dict[str, Decimal],
    previous: dict[str, Decimal],
) -> dict:
    values = {name: current.get(code) for name, code in ITEM_CODES.items()}
    previous_values = {name: previous.get(code) for name, code in ITEM_CODES.items()}
    ebitda_proxy = None
    if values["operating_profit"] is not None and values["depreciation"] is not None:
        ebitda_proxy = values["operating_profit"] + values["depreciation"]
    total_debt = None
    if values["short_term_debt"] is not None or values["long_term_debt"] is not None:
        total_debt = (values["short_term_debt"] or 0) + (values["long_term_debt"] or 0)

    ratios = {
        "revenue_yoy": _year_over_year(values["revenue"], previous_values["revenue"]),
        "net_income_yoy": _year_over_year(values["net_income"], previous_values["net_income"]),
        "gross_margin": _safe_div(values["gross_profit"], values["revenue"]),
        "operating_margin": _safe_div(values["operating_profit"], values["revenue"]),
        "net_margin": _safe_div(values["net_income"], values["revenue"]),
        "current_ratio": _safe_div(values["current_assets"], values["current_liabilities"]),
        "debt_to_equity": _safe_div(total_debt, values["equity"]),
        "cash_to_debt": _safe_div(values["cash"], total_debt),
        "annualized_roe": _safe_div(
            values["net_income"] * Decimal(12) / Decimal(period)
            if values["net_income"] is not None
            else None,
            values["equity"],
        ),
        "operating_cash_flow_margin": _safe_div(values["operating_cash_flow"], values["revenue"]),
        "free_cash_flow_margin": _safe_div(values["free_cash_flow"], values["revenue"]),
    }
    components = {
        "growth": _average(
            [
                _linear_score(ratios["revenue_yoy"], "-0.30", "0.30"),
                _linear_score(ratios["net_income_yoy"], "-0.50", "0.50"),
            ]
        ),
        "profitability": _average(
            [
                _linear_score(ratios["gross_margin"], "-0.10", "0.40"),
                _linear_score(ratios["operating_margin"], "-0.10", "0.25"),
                _linear_score(ratios["net_margin"], "-0.10", "0.20"),
                _linear_score(ratios["annualized_roe"], "-0.10", "0.30"),
            ]
        ),
        "balance_sheet": _average(
            [
                _linear_score(ratios["current_ratio"], "0.50", "2.00"),
                _linear_score(ratios["debt_to_equity"], "0", "3", inverse=True),
                _linear_score(ratios["cash_to_debt"], "0", "0.50"),
            ]
        ),
        "cash_flow": _average(
            [
                _linear_score(ratios["operating_cash_flow_margin"], "-0.10", "0.20"),
                _linear_score(ratios["free_cash_flow_margin"], "-0.10", "0.15"),
            ]
        ),
    }
    available_components = [value for value in components.values() if value is not None]
    completeness = sum(value is not None for value in ratios.values())
    score = (
        Decimal(str(round(sum(available_components) / len(available_components), 2)))
        if completeness >= 6 and len(available_components) >= 3
        else None
    )
    return {
        "ticker": ticker,
        "financial_group": financial_group,
        "exchange": exchange,
        "year": year,
        "period": period,
        "revenue": values["revenue"],
        "gross_profit": values["gross_profit"],
        "operating_profit": values["operating_profit"],
        "ebitda_proxy": ebitda_proxy,
        "net_income": values["net_income"],
        "operating_cash_flow": values["operating_cash_flow"],
        "free_cash_flow": values["free_cash_flow"],
        "current_assets": values["current_assets"],
        "cash": values["cash"],
        "current_liabilities": values["current_liabilities"],
        "short_term_debt": values["short_term_debt"],
        "long_term_debt": values["long_term_debt"],
        "equity": values["equity"],
        **ratios,
        "fundamental_score": score,
        "score_components": {
            key: round(value, 2) if value is not None else None for key, value in components.items()
        },
        "data_completeness": completeness,
    }


def build_snapshots(facts: list[FinancialFact | dict[str, Any]]) -> list[dict]:
    by_period: dict[tuple[str, str, str, int, int], dict[str, Decimal]] = {}
    for fact in facts:
        if isinstance(fact, dict):
            get = fact.get
        else:
            get = lambda name, row=fact: getattr(row, name)
        key = (get("ticker"), get("financial_group"), get("exchange"), get("year"), get("period"))
        by_period.setdefault(key, {})[get("item_code")] = get("value")

    snapshots: list[dict] = []
    for (ticker, group, exchange, year, period), current in sorted(by_period.items()):
        if not any(code in current for code in ITEM_CODES.values()):
            continue
        previous = by_period.get((ticker, group, exchange, year - 1, period), {})
        snapshots.append(
            calculate_fundamental_snapshot(
                ticker=ticker,
                financial_group=group,
                exchange=exchange,
                year=year,
                period=period,
                current=current,
                previous=previous,
            )
        )
    return snapshots


class FundamentalsCollector(BaseCollector):
    name = "fundamentals"

    def __init__(
        self,
        session: AsyncSession,
        *,
        tickers: list[str] | None = None,
        years: list[int] | None = None,
    ) -> None:
        super().__init__(rate_limit_per_sec=1.0)
        current_year = datetime.now(UTC).year
        self._session = session
        self._tickers = sorted(
            {ticker.upper().strip() for ticker in tickers or [] if ticker.strip()}
        )
        self._years = sorted(set(years or [current_year - 1, current_year]))

    async def _resolve_tickers(self) -> list[str]:
        active = set(
            (
                await self._session.scalars(
                    select(Instrument.ticker).where(Instrument.is_active.is_(True))
                )
            ).all()
        )
        if self._tickers:
            return sorted(set(self._tickers) & active)
        since = datetime.now(UTC) - timedelta(days=30)
        rows = (
            await self._session.scalars(
                select(LlmEvaluation.ticker_codes).where(
                    LlmEvaluation.status == "succeeded",
                    LlmEvaluation.relevance_score >= 60,
                    LlmEvaluation.completed_at >= since,
                )
            )
        ).all()
        return sorted({ticker for codes in rows for ticker in codes if ticker in active})[:50]

    @staticmethod
    def _params(ticker: str, group: str, year: int) -> dict:
        params: dict[str, str | int] = {
            "companyCode": ticker,
            "exchange": "TRY",
            "financialGroup": group,
        }
        for slot, period in enumerate(PERIODS, start=1):
            params[f"year{slot}"] = year
            params[f"period{slot}"] = period
        return params

    async def _fetch_group(self, ticker: str) -> tuple[str, dict[int, dict]]:
        cached: dict[int, dict] = {}
        for group in FINANCIAL_GROUPS:
            for year in sorted(self._years, reverse=True):
                payload = await self.get_json(
                    FINANCIALS_URL, params=self._params(ticker, group, year)
                )
                rows = map_financial_response(ticker, group, year, payload)
                if rows:
                    cached[year] = payload
                    return group, cached
        raise CollectorError(f"{ticker} icin desteklenen finansal tablo grubu bulunamadi")

    async def run(self) -> dict:
        tickers = await self._resolve_tickers()
        if not tickers:
            return {
                "requested": 0,
                "processed": 0,
                "facts": 0,
                "new": 0,
                "snapshots": 0,
                "failures": {},
            }
        failures: dict[str, str] = {}
        processed = facts_count = new_count = snapshots_count = 0

        for ticker in tickers:
            try:
                group, payloads = await self._fetch_group(ticker)
                mapped: list[dict] = []
                for year in self._years:
                    payload = payloads.get(year)
                    if payload is None:
                        payload = await self.get_json(
                            FINANCIALS_URL, params=self._params(ticker, group, year)
                        )
                    mapped.extend(map_financial_response(ticker, group, year, payload))
                identities = [
                    (
                        row["ticker"],
                        row["financial_group"],
                        row["exchange"],
                        row["year"],
                        row["period"],
                        row["item_code"],
                    )
                    for row in mapped
                ]
                existing: set[tuple] = set()
                if identities:
                    result = await self._session.execute(
                        select(
                            FinancialFact.ticker,
                            FinancialFact.financial_group,
                            FinancialFact.exchange,
                            FinancialFact.year,
                            FinancialFact.period,
                            FinancialFact.item_code,
                        ).where(
                            FinancialFact.ticker == ticker,
                            FinancialFact.financial_group == group,
                            FinancialFact.year.in_(self._years),
                        )
                    )
                    existing = set(result.all())
                for fields in mapped:
                    stmt = pg_insert(FinancialFact).values(**fields)
                    stmt = stmt.on_conflict_do_update(
                        constraint="uq_financial_fact_identity",
                        set_={
                            "item_name_tr": stmt.excluded.item_name_tr,
                            "item_name_en": stmt.excluded.item_name_en,
                            "value": stmt.excluded.value,
                            "raw_value": stmt.excluded.raw_value,
                            "fetched_at": func.now(),
                            "updated_at": func.now(),
                        },
                    )
                    await self._session.execute(stmt)
                await self._session.commit()

                facts = (
                    await self._session.scalars(
                        select(FinancialFact).where(
                            FinancialFact.ticker == ticker,
                            FinancialFact.financial_group == group,
                            FinancialFact.exchange == "TRY",
                            FinancialFact.year.in_(self._years),
                        )
                    )
                ).all()
                snapshots = build_snapshots(list(facts))
                for fields in snapshots:
                    stmt = pg_insert(FundamentalSnapshot).values(**fields)
                    update_fields = {
                        key: getattr(stmt.excluded, key)
                        for key in fields
                        if key not in {"ticker", "financial_group", "exchange", "year", "period"}
                    }
                    update_fields["computed_at"] = func.now()
                    update_fields["updated_at"] = func.now()
                    await self._session.execute(
                        stmt.on_conflict_do_update(
                            constraint="uq_fundamental_snapshot_identity", set_=update_fields
                        )
                    )
                await self._session.commit()
                facts_count += len(mapped)
                new_count += len(set(identities) - existing)
                snapshots_count += len(snapshots)
                processed += 1
            except Exception as exc:  # noqa: BLE001 - tek sirket digerlerini durdurmasin
                await self._session.rollback()
                failures[ticker] = str(exc)
                self.log.error("fundamentals_ticker_failed", ticker=ticker, error=str(exc))

        return {
            "requested": len(tickers),
            "processed": processed,
            "facts": facts_count,
            "new": new_count,
            "snapshots": snapshots_count,
            "failures": failures,
        }
