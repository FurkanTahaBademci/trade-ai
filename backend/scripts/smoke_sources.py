"""Faz 0 kaynak dogrulama script'i.

Plana gore kod yazmadan once her veri kaynaginin gercekten canli oldugunu
ve beklenen semayla dondugunu dogrulamamiz gerekiyor. Bu script agdaki
gercek servislere tek seferlik istekler atar ve sonucu ozetler.

Calistirma:
    docker compose exec api python -m scripts.smoke_sources
    (veya lokal venv'de) python -m scripts.smoke_sources

Cikis kodu: tum kontroller basariliysa 0, herhangi biri basarisizsa 1
(CI/monitoring'de kullanilabilsin diye).
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.core.config import get_settings

settings = get_settings()

HEADERS = {"User-Agent": settings.collector_user_agent}
ISTANBUL = ZoneInfo("Europe/Istanbul")


def _today():
    return datetime.now(ISTANBUL).date()


@dataclass
class SourceCheck:
    name: str
    ok: bool
    detail: str
    sample_keys: list[str] = field(default_factory=list)


async def check_kap_disclosure_list(client: httpx.AsyncClient) -> SourceCheck:
    """KAP bildirim listesi — POST /tr/api/disclosure/members/byCriteria.

    Referer + User-Agent zorunlu; dar bir tarih penceresi kullaniyoruz ki
    2000 kayit limitine takilmayalim.
    """
    name = "kap_disclosure_list"
    url = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"
    today = _today()
    payload = {
        "fromDate": (today - timedelta(days=1)).isoformat(),
        "toDate": today.isoformat(),
        "mkkMemberOidList": [],
        "subjectList": [],
    }
    headers = {
        **HEADERS,
        "Referer": "https://www.kap.org.tr/tr/bildirim-sorgu",
        "Content-Type": "application/json",
    }
    try:
        resp = await client.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return SourceCheck(name, False, f"beklenmeyen govde tipi: {type(data)}")
        sample_keys = list(data[0].keys()) if data else []
        return SourceCheck(name, True, f"{len(data)} bildirim dondu", sample_keys)
    except Exception as exc:  # noqa: BLE001
        return SourceCheck(name, False, f"hata: {exc!r}")


async def check_kap_disclosure_detail(client: httpx.AsyncClient) -> SourceCheck:
    """Onceki adimda bulunan ilk bildirimin detayini cek.

    Liste bos donerse (hafta sonu / tatil) bu kontrol atlanir — hata sayilmaz.
    """
    name = "kap_disclosure_detail"
    list_check = await check_kap_disclosure_list(client)
    if not list_check.ok:
        return SourceCheck(name, False, "liste alinamadigi icin atlandi")

    # Listeyi tekrar cekip disclosureIndex al (check_kap_disclosure_list detayi donmuyor)
    today = _today()
    url_list = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"
    payload = {
        "fromDate": (today - timedelta(days=3)).isoformat(),
        "toDate": today.isoformat(),
        "mkkMemberOidList": [],
        "subjectList": [],
    }
    headers = {
        **HEADERS,
        "Referer": "https://www.kap.org.tr/tr/bildirim-sorgu",
        "Content-Type": "application/json",
    }
    try:
        resp = await client.post(url_list, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        items = resp.json()
        if not items:
            return SourceCheck(name, True, "son 3 gunde bildirim yok, detay testi atlandi (uyari degil)")

        disclosure_index = items[0].get("disclosureIndex") or items[0].get("basicDisclosureIndex")
        if not disclosure_index:
            return SourceCheck(name, False, f"disclosureIndex alani bulunamadi: {list(items[0].keys())}")

        detail_url = f"https://www.kap.org.tr/tr/api/notification/attachment-detail/{disclosure_index}"
        detail_headers = {
            **HEADERS,
            "Referer": f"https://www.kap.org.tr/tr/Bildirim/{disclosure_index}",
        }
        detail_resp = await client.get(detail_url, headers=detail_headers, timeout=15)
        detail_resp.raise_for_status()
        detail_data = detail_resp.json()
        return SourceCheck(name, True, f"detay alindi (index={disclosure_index})", list(detail_data[0].keys()) if isinstance(detail_data, list) and detail_data else [])
    except Exception as exc:  # noqa: BLE001
        return SourceCheck(name, False, f"hata: {exc!r}")


async def check_tefas(client: httpx.AsyncClient) -> SourceCheck:
    """TEFAS fon portfoy dagilim API'si (Takasbank resmi).

    Endpoint ve tam govde alanlari pytefas kutuphanesinin ham kaynagindan
    (github.com/mirzazad/pytefas/blob/main/pytefas/client.py) birebir
    dogrulandi: POST + JSON govde, tarih format %Y%m%d, basSira/bitSira int.
    """
    name = "tefas_fund_allocation"
    url = "https://www.tefas.gov.tr/api/funds/dagilimSiraliGetirT"
    today = _today()
    payload = {
        "fonTipi": "YAT",
        "fonKodu": None,
        "aramaMetni": None,
        "fonTurKod": None,
        "fonGrubu": None,
        "sfonTurKod": None,
        "fonTurAciklama": None,
        "kurucuKod": None,
        "basTarih": (today - timedelta(days=3)).strftime("%Y%m%d"),
        "bitTarih": today.strftime("%Y%m%d"),
        "basSira": 1,
        "bitSira": 20,
        "dil": "TR",
        "sFonTurKod": "",
        "fonKod": "",
        "fonGrup": "",
        "fonUnvanTip": "",
    }
    headers = {
        **HEADERS,
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://www.tefas.gov.tr",
        "Referer": "https://www.tefas.gov.tr/tr/fon-verileri",
    }
    try:
        resp = await client.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errorCode"):
            return SourceCheck(name, False, f"API hata dondu: {data.get('errorMessage')}")
        rows = data.get("resultList", [])
        sample_keys = list(rows[0].keys()) if rows else []
        return SourceCheck(name, True, f"{len(rows)} satir dondu", sample_keys)
    except Exception as exc:  # noqa: BLE001
        return SourceCheck(name, False, f"hata: {exc!r} (endpoint/parametreler dogrulanmali)")


async def check_isyatirimhisse() -> SourceCheck:
    """isyatirimhisse kutuphanesi ile bir hisse icin fiyat verisi cek."""
    name = "isyatirimhisse_prices"
    try:
        from isyatirimhisse import fetch_stock_data  # type: ignore
    except ImportError:
        try:
            from isyatirimhisse import StockData  # type: ignore

            def fetch_stock_data(symbols, start_date, end_date):  # type: ignore
                return StockData().get_data(symbols=symbols, start_date=start_date, end_date=end_date)
        except ImportError as exc:
            return SourceCheck(name, False, f"kutuphane import edilemedi: {exc!r}")

    try:
        today = _today()
        start = (today - timedelta(days=10)).strftime("%d-%m-%Y")
        end = today.strftime("%d-%m-%Y")
        result = await asyncio.to_thread(fetch_stock_data, ["THYAO"], start, end)
        row_count = len(result) if hasattr(result, "__len__") else "bilinmiyor"
        return SourceCheck(name, True, f"THYAO icin veri alindi, satir sayisi={row_count}")
    except Exception as exc:  # noqa: BLE001
        return SourceCheck(name, False, f"hata: {exc!r} (kutuphane API'si degismis olabilir)")


RSS_FEEDS = {
    "bloomberght": "https://www.bloomberght.com/rss",
    "investing_tr": "https://tr.investing.com/rss/news.rss",
}


async def check_rss_feed(client: httpx.AsyncClient, name: str, url: str) -> SourceCheck:
    check_name = f"rss_{name}"
    try:
        resp = await client.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        import feedparser

        parsed = feedparser.parse(resp.content)
        entry_count = len(parsed.entries)
        if entry_count == 0:
            return SourceCheck(check_name, False, "feed parse edildi ama 0 entry - feed olmus veya format degismis")
        sample = list(parsed.entries[0].keys()) if entry_count else []
        return SourceCheck(check_name, True, f"{entry_count} haber bulundu", sample)
    except Exception as exc:  # noqa: BLE001
        return SourceCheck(check_name, False, f"hata: {exc!r}")


async def main() -> int:
    checks: list[SourceCheck] = []

    async with httpx.AsyncClient() as client:
        checks.append(await check_kap_disclosure_list(client))
        checks.append(await check_kap_disclosure_detail(client))
        checks.append(await check_tefas(client))
        for name, url in RSS_FEEDS.items():
            checks.append(await check_rss_feed(client, name, url))

    checks.append(await check_isyatirimhisse())

    print("\n=== Kaynak Dogrulama Raporu ===\n")
    all_ok = True
    for c in checks:
        status = "OK" if c.ok else "FAIL"
        if not c.ok:
            all_ok = False
        print(f"[{status}] {c.name}: {c.detail}")
        if c.sample_keys:
            print(f"      alanlar: {', '.join(c.sample_keys[:15])}")

    print()
    if all_ok:
        print("Tum kaynaklar canli. Faz 1'e gecilebilir.")
    else:
        print("BAZI KAYNAKLAR BASARISIZ. Faz 1'e gecmeden once yukaridaki hatalari incele -")
        print("endpoint/kutuphane API'si degismis olabilir, plan buna gore revize edilmeli.")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
