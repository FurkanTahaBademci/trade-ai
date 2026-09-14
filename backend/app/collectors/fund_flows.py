"""TEFAS gunluk fon snapshot'lari ve getiri-duzeltilmis akim tahmini."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import json
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.collectors.base import BaseCollector, CollectorError
from app.core.config import get_settings
from app.models import FundFlowAggregate, FundSnapshot

TEFAS_INFO_URL = "https://www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetir"
TEFAS_ALLOCATION_URL = "https://www.tefas.gov.tr/api/funds/dagilimSiraliGetirT"
TEFAS_HEADERS = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    "Origin": "https://www.tefas.gov.tr",
    "Referer": "https://www.tefas.gov.tr/tr/fon-verileri",
    "Connection": "close",
}
FUND_KINDS = {"YAT", "EMK", "BYF", "GYF", "GSYF"}


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise CollectorError(f"TEFAS sayisal alani gecersiz: {value!r}") from exc


def _rows(payload: dict | list, source: str) -> list[dict]:
    if not isinstance(payload, dict):
        raise CollectorError(f"TEFAS {source} yaniti nesne degil")
    error = payload.get("errorCode") or payload.get("errorMessage")
    if error:
        raise CollectorError(f"TEFAS {source} hatasi: {error}")
    rows = payload.get("resultList")
    if not isinstance(rows, list):
        raise CollectorError(f"TEFAS {source} resultList icermiyor")
    return [row for row in rows if isinstance(row, dict)]


def map_tefas_snapshots(
    info_payload: dict | list,
    allocation_payload: dict | list,
    *,
    fund_kind: str = "YAT",
) -> list[dict]:
    allocations = {
        (str(row.get("fonKodu") or "").strip().upper(), str(row.get("tarih") or "")): row
        for row in _rows(allocation_payload, "dagilim")
    }
    mapped: list[dict] = []
    for row in _rows(info_payload, "genel bilgi"):
        fund_code = str(row.get("fonKodu") or "").strip().upper()
        raw_date = str(row.get("tarih") or "")
        fund_name = str(row.get("fonUnvan") or "").strip()
        if not fund_code or not raw_date or not fund_name:
            continue
        try:
            snapshot_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise CollectorError(f"TEFAS tarih formati degisti: {raw_date!r}") from exc
        allocation = allocations.get((fund_code, raw_date))
        mapped.append(
            {
                "fund_kind": fund_kind,
                "fund_code": fund_code,
                "date": snapshot_date,
                "fund_name": fund_name,
                "price": _decimal(row.get("fiyat")),
                "shares_outstanding": _decimal(row.get("tedPaySayisi")),
                "investor_count": int(row["kisiSayisi"])
                if row.get("kisiSayisi") is not None
                else None,
                "portfolio_size": _decimal(row.get("portfoyBuyukluk")),
                "exchange_bulletin_price": _decimal(row.get("borsaBultenFiyat")),
                "stock_pct": _decimal(allocation.get("hs")) if allocation else None,
                "foreign_stock_pct": _decimal(allocation.get("yhs")) if allocation else None,
                "estimated_net_flow": None,
                "estimated_stock_flow": None,
                "raw_info": row,
                "raw_allocation": allocation,
            }
        )
    if not mapped:
        raise CollectorError("TEFAS genel bilgi yanitinda kullanilabilir satir yok")
    return mapped


def calculate_fund_flows(rows: list[FundSnapshot | dict[str, Any]]) -> list[dict]:
    def get(row, key):
        return row.get(key) if isinstance(row, dict) else getattr(row, key)

    grouped: dict[tuple[str, str], list] = defaultdict(list)
    for row in rows:
        grouped[(get(row, "fund_kind"), get(row, "fund_code"))].append(row)

    calculated: list[dict] = []
    for fund_rows in grouped.values():
        previous = None
        for row in sorted(fund_rows, key=lambda item: get(item, "date")):
            net_flow = stock_flow = None
            aum = get(row, "portfolio_size")
            price = get(row, "price")
            if previous is not None:
                previous_aum = get(previous, "portfolio_size")
                previous_price = get(previous, "price")
                if (
                    aum is not None
                    and price is not None
                    and previous_aum is not None
                    and previous_price
                ):
                    net_flow = aum - (previous_aum * price / previous_price)
                    stock_pct = get(row, "stock_pct") or Decimal(0)
                    stock_flow = net_flow * stock_pct / Decimal(100)
            calculated.append(
                {
                    "fund_kind": get(row, "fund_kind"),
                    "fund_code": get(row, "fund_code"),
                    "date": get(row, "date"),
                    "estimated_net_flow": net_flow,
                    "estimated_stock_flow": stock_flow,
                }
            )
            previous = row
    return calculated


def aggregate_fund_flows(rows: list[FundSnapshot | dict[str, Any]]) -> list[dict]:
    def get(row, key):
        return row.get(key) if isinstance(row, dict) else getattr(row, key)

    grouped: dict[tuple[str, date], list] = defaultdict(list)
    for row in rows:
        grouped[(get(row, "fund_kind"), get(row, "date"))].append(row)
    output: list[dict] = []
    for (kind, snapshot_date), date_rows in sorted(grouped.items()):
        aums = [get(row, "portfolio_size") for row in date_rows if get(row, "portfolio_size")]
        flows = [
            get(row, "estimated_net_flow")
            for row in date_rows
            if get(row, "estimated_net_flow") is not None
        ]
        stock_flows = [
            get(row, "estimated_stock_flow")
            for row in date_rows
            if get(row, "estimated_stock_flow") is not None
        ]
        stock_exposure = sum(
            (
                (get(row, "portfolio_size") or Decimal(0))
                * (get(row, "stock_pct") or Decimal(0))
                / Decimal(100)
                for row in date_rows
            ),
            Decimal(0),
        )
        output.append(
            {
                "fund_kind": kind,
                "date": snapshot_date,
                "fund_count": len(date_rows),
                "flow_observation_count": len(flows),
                "total_aum": sum(aums, Decimal(0)),
                "total_net_flow": sum(flows, Decimal(0)) if flows else None,
                "total_stock_exposure": stock_exposure,
                "estimated_stock_flow": sum(stock_flows, Decimal(0)) if stock_flows else None,
                "positive_flow_pct": (
                    Decimal(sum(flow > 0 for flow in flows)) / Decimal(len(flows)) * 100
                    if flows
                    else None
                ),
            }
        )
    return output


class FundFlowCollector(BaseCollector):
    name = "fund_flows"

    def __init__(
        self,
        session: AsyncSession,
        *,
        fund_kind: str = "YAT",
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> None:
        # TEFAS dokumante edilmemis genel API'sinde koruyucu olarak 6 istek/dk.
        super().__init__(rate_limit_per_sec=0.1)
        kind = fund_kind.upper()
        if kind not in FUND_KINDS:
            raise ValueError(f"Gecersiz fon tipi: {fund_kind}")
        today = datetime.now(ZoneInfo("Europe/Istanbul")).date()
        self._session = session
        self._fund_kind = kind
        self._start_date = start_date or today - timedelta(days=7)
        self._end_date = end_date or today
        if self._end_date < self._start_date:
            raise ValueError("Fon akimi bitis tarihi baslangictan once olamaz")
        if (self._end_date - self._start_date).days > 27:
            raise ValueError("TEFAS tek kosuda en fazla 28 gun kabul eder")

    def _payload(self) -> dict:
        return {
            "fonTipi": self._fund_kind,
            "fonKodu": None,
            "aramaMetni": None,
            "fonTurKod": None,
            "fonGrubu": None,
            "sfonTurKod": None,
            "fonTurAciklama": None,
            "kurucuKod": None,
            "basTarih": self._start_date.strftime("%Y%m%d"),
            "bitTarih": self._end_date.strftime("%Y%m%d"),
            "basSira": 1,
            "bitSira": 100000,
            "dil": "TR",
            "sFonTurKod": "",
            "fonKod": "",
            "fonGrup": "",
            "fonUnvanTip": "",
        }

    @retry(
        retry=retry_if_exception_type((
            httpx.TransportError,
            httpx.HTTPStatusError,
            httpx.TimeoutException,
            json.JSONDecodeError,
        )),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def _post_tefas(self, url: str, payload: dict) -> dict:
        await self._throttle()
        async with httpx.AsyncClient(
            headers={
                **TEFAS_HEADERS,
                "User-Agent": get_settings().collector_user_agent,
            },
            timeout=httpx.Timeout(60.0, connect=15.0),
            verify=False,
        ) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                self.log.warning(
                    "tefas_http_request_retry",
                    url=url,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                raise

    async def run(self) -> dict:
        info = await self._post_tefas(TEFAS_INFO_URL, self._payload())
        allocation = await self._post_tefas(TEFAS_ALLOCATION_URL, self._payload())
        mapped = map_tefas_snapshots(info, allocation, fund_kind=self._fund_kind)
        identities = {(row["fund_code"], row["date"]) for row in mapped}
        existing = set(
            (
                await self._session.execute(
                    select(FundSnapshot.fund_code, FundSnapshot.date).where(
                        FundSnapshot.fund_kind == self._fund_kind,
                        FundSnapshot.date.between(self._start_date, self._end_date),
                    )
                )
            ).all()
        )
        for offset in range(0, len(mapped), 1_000):
            batch = mapped[offset : offset + 1_000]
            stmt = pg_insert(FundSnapshot).values(batch)
            await self._session.execute(
                stmt.on_conflict_do_update(
                    constraint="uq_fund_snapshot_identity",
                    set_={
                        "fund_name": stmt.excluded.fund_name,
                        "price": stmt.excluded.price,
                        "shares_outstanding": stmt.excluded.shares_outstanding,
                        "investor_count": stmt.excluded.investor_count,
                        "portfolio_size": stmt.excluded.portfolio_size,
                        "exchange_bulletin_price": stmt.excluded.exchange_bulletin_price,
                        "stock_pct": func.coalesce(stmt.excluded.stock_pct, FundSnapshot.stock_pct),
                        "foreign_stock_pct": func.coalesce(
                            stmt.excluded.foreign_stock_pct, FundSnapshot.foreign_stock_pct
                        ),
                        "raw_info": stmt.excluded.raw_info,
                        "raw_allocation": func.coalesce(
                            stmt.excluded.raw_allocation, FundSnapshot.raw_allocation
                        ),
                        "fetched_at": func.now(),
                        "updated_at": func.now(),
                    },
                )
            )
        await self._session.commit()

        history_start = self._start_date - timedelta(days=10)
        snapshots = list(
            (
                await self._session.scalars(
                    select(FundSnapshot)
                    .where(
                        FundSnapshot.fund_kind == self._fund_kind,
                        FundSnapshot.date >= history_start,
                        FundSnapshot.date <= self._end_date,
                    )
                    .order_by(FundSnapshot.fund_code, FundSnapshot.date)
                )
            ).all()
        )
        by_identity = {(row.fund_kind, row.fund_code, row.date): row for row in snapshots}
        for fields in calculate_fund_flows(snapshots):
            row = by_identity[(fields["fund_kind"], fields["fund_code"], fields["date"])]
            row.estimated_net_flow = fields["estimated_net_flow"]
            row.estimated_stock_flow = fields["estimated_stock_flow"]
        await self._session.commit()

        current_rows = [row for row in snapshots if row.date >= self._start_date]
        aggregates = aggregate_fund_flows(current_rows)
        if aggregates:
            stmt = pg_insert(FundFlowAggregate).values(aggregates)
            update_fields = {
                key: getattr(stmt.excluded, key)
                for key in aggregates[0]
                if key not in {"fund_kind", "date"}
            }
            update_fields["computed_at"] = func.now()
            update_fields["updated_at"] = func.now()
            await self._session.execute(
                stmt.on_conflict_do_update(
                    constraint="uq_fund_flow_aggregate_identity", set_=update_fields
                )
            )
            await self._session.commit()
        return {
            "fund_kind": self._fund_kind,
            "snapshots": len(mapped),
            "new": len(identities - existing),
            "with_allocation": sum(row["raw_allocation"] is not None for row in mapped),
            "flow_aggregates": len(aggregates),
        }
