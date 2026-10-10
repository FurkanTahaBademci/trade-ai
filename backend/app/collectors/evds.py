"""TCMB EVDS makro seri toplayicisi (USD/TRY, EUR/TRY, TUFE endeksi).

Uc nokta: `https://evds2.tcmb.gov.tr/service/evds/series=A-B&startDate=dd-mm-yyyy
&endDate=dd-mm-yyyy&type=json`. Parametreler sorgu dizesi degil yol parcasidir
("?" yok). API anahtari `key` HTTP basligiyla gider; anahtarsiz istek 302 doner.
Yanit `items` listesidir: her satirda `Tarih` ve seri kodunun noktalari alt
cizgiye cevrilmis anahtarlari (TP.DK.USD.A.YTL -> TP_DK_USD_A_YTL) bulunur.

NOT: Gelistirme sirasinda API anahtari olmadigi icin gercek yanit fixture'i
kaydedilemedi; tests/fixtures/evds/series_sample.json belgelenen bicimle
uretilmis SENTETIK bir ornektir. Anahtar alininca
`python -m scripts.run_once evds --save-fixture` ile gercek yanitla degistirin.

Idempotency: (series_code, date) dogal anahtari uzerinden ON CONFLICT DO UPDATE.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector, CollectorError
from app.core.config import get_settings
from app.models import MacroSeriesPoint

EVDS_BASE_URL = "https://evds2.tcmb.gov.tr/service/evds/"
# Kod -> gorunen ad. TUFE endeksinden yillik degisim API tarafinda hesaplanir.
EVDS_SERIES: dict[str, str] = {
    "TP.DK.USD.A.YTL": "USD/TRY (TCMB alış)",
    "TP.DK.EUR.A.YTL": "EUR/TRY (TCMB alış)",
    "TP.FG.J0": "TÜFE (2003=100)",
}
# Yillik TUFE degisimi icin 13 aylik gozlem gerekir.
LOOKBACK_DAYS = 430

_DAILY = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
_MONTHLY = re.compile(r"(\d{4})-(\d{1,2})")


def build_series_url(codes: list[str], start: date, end: date) -> str:
    return (
        f"{EVDS_BASE_URL}series={'-'.join(codes)}"
        f"&startDate={start:%d-%m-%Y}&endDate={end:%d-%m-%Y}&type=json"
    )


def parse_evds_date(raw: str) -> date | None:
    text = raw.strip()
    if match := _DAILY.fullmatch(text):
        day, month, year = (int(part) for part in match.groups())
        return date(year, month, day)
    if match := _MONTHLY.fullmatch(text):
        year, month = (int(part) for part in match.groups())
        return date(year, month, 1)
    return None


def map_series_response(payload: dict | list, codes: list[str]) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise CollectorError("EVDS yaniti items listesi icermiyor")
    rows: list[dict] = []
    for item in payload["items"]:
        if not isinstance(item, dict):
            continue
        observed = parse_evds_date(str(item.get("Tarih") or ""))
        if observed is None:
            continue
        for code in codes:
            raw = item.get(code.replace(".", "_"))
            if raw in (None, "", "ND"):
                continue
            try:
                value = Decimal(str(raw).replace(",", "."))
            except InvalidOperation:
                continue
            rows.append({"series_code": code, "date": observed, "value": value})
    return rows


class EvdsCollector(BaseCollector):
    name = "evds"

    def __init__(self, session: AsyncSession, *, days: int = LOOKBACK_DAYS) -> None:
        super().__init__(rate_limit_per_sec=1.0)
        self._session = session
        self._days = days

    async def fetch_raw(self) -> dict | list:
        key = get_settings().evds_api_key
        end = datetime.now(UTC).date()
        start = end - timedelta(days=self._days)
        return await self.get_json(
            build_series_url(list(EVDS_SERIES), start, end), headers={"key": key}
        )

    async def run(self) -> dict:
        if not get_settings().evds_api_key:
            return {"skipped": "EVDS_API_KEY tanimli degil", "rows": 0}
        rows = map_series_response(await self.fetch_raw(), list(EVDS_SERIES))
        if not rows:
            raise CollectorError("EVDS yaniti hic gozlem icermiyor")
        stmt = pg_insert(MacroSeriesPoint).values(rows)
        await self._session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_macro_series_point_identity",
                set_={"value": stmt.excluded.value, "fetched_at": func.now()},
            )
        )
        await self._session.commit()
        return {"rows": len(rows), "series": sorted({row["series_code"] for row in rows})}


def save_fixture(payload: dict | list, path: Path) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
