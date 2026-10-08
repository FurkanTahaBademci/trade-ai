"""Resmi TCMB PPK takvimi ve karar metni collector'i."""

from __future__ import annotations

import html
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from html.parser import HTMLParser
from urllib.parse import urljoin

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector
from app.models import MonetaryPolicyDecision

BASE_URL = "https://www.tcmb.gov.tr"
CALENDAR_URL = f"{BASE_URL}/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Temel+Faaliyetler/Para+Politikasi/PPK/{{year}}"

MONTHS = {
    "ocak": 1,
    "subat": 2,
    "şubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayis": 5,
    "mayıs": 5,
    "haziran": 6,
    "temmuz": 7,
    "agustos": 8,
    "ağustos": 8,
    "eylul": 9,
    "eylül": 9,
    "ekim": 10,
    "kasim": 11,
    "kasım": 11,
    "aralik": 12,
    "aralık": 12,
}


def _clean(value: str) -> str:
    return " ".join(html.unescape(value).replace("\xa0", " ").split())


def parse_turkish_date(value: str) -> date | None:
    match = re.search(r"(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(\d{4})", _clean(value))
    if not match:
        return None
    month = MONTHS.get(match.group(2).casefold())
    return date(int(match.group(3)), month, int(match.group(1))) if month else None


class CalendarParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.in_body = False
        self.in_cell = False
        self.cell_index = -1
        self.text: list[str] = []
        self.href: str | None = None
        self.rows: list[tuple[date, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "table" and values.get("id") == "midTable":
            self.in_table = True
        elif self.in_table and tag == "tbody":
            self.in_body = True
        elif self.in_body and tag == "tr":
            self.cell_index = -1
        elif self.in_body and tag == "td":
            self.cell_index += 1
            self.in_cell = self.cell_index == 0
            if self.in_cell:
                self.text, self.href = [], None
        elif self.in_cell and tag == "a":
            self.href = values.get("href")

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_cell:
            parsed = parse_turkish_date("".join(self.text))
            if parsed:
                self.rows.append((parsed, urljoin(BASE_URL, self.href) if self.href else None))
            self.in_cell = False
        elif tag == "tbody" and self.in_body:
            self.in_body = False
        elif tag == "table" and self.in_table:
            self.in_table = False


class DecisionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.capture = False
        self.current: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "div" and values.get("id") == "tcmbMainContent":
            self.depth = 1
        elif self.depth and tag == "div":
            self.depth += 1
        if self.depth and tag in {"p", "h2"}:
            self.capture, self.current = True, []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.current.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.capture and tag in {"p", "h2"}:
            value = _clean("".join(self.current))
            if value:
                self.blocks.append(value)
            self.capture = False
        if self.depth and tag == "div":
            self.depth -= 1


def parse_calendar(content: str) -> list[tuple[date, str | None]]:
    parser = CalendarParser()
    parser.feed(content)
    return parser.rows


def _rates_after(label: str, stop: str, text: str) -> list[Decimal]:
    match = re.search(rf"{label}(.+?){stop}", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    return [
        Decimal(value.replace(",", "."))
        for value in re.findall(r"yüzde\s+(\d+(?:[,.]\d+)?)", match.group(1), re.IGNORECASE)
    ]


def _policy_rates(text: str) -> list[Decimal]:
    transition = re.search(
        r"politika faizi olan.+?oran(?:ının|ını) yüzde\s+(\d+(?:[,.]\d+)?).{0,18}?"
        r"yüzde\s+(\d+(?:[,.]\d+)?)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if transition:
        return [Decimal(value.replace(",", ".")) for value in transition.groups()]
    current = re.search(
        r"politika faizi olan.+?oran(?:ının|ını) yüzde\s+(\d+(?:[,.]\d+)?)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return [Decimal(current.group(1).replace(",", "."))] if current else []


def build_market_impact(decision_type: str, change_bps: int | None) -> dict:
    scenarios = {
        "CUT": {
            "overall": "Destekleyici",
            "equities": "Iskonto oranı ve finansman maliyeti kanalıyla destekleyici olabilir.",
            "banks": "Kredi büyümesi desteklenebilir; marj etkisi kararın sürprizine bağlıdır.",
            "real_estate": "Finansman hassasiyeti nedeniyle göreli pozitif etki görülebilir.",
            "try": "Beklentiden hızlı indirim Türk lirasında baskı oluşturabilir.",
            "bonds": "Getirilerde düşüş ve tahvil fiyatlarında yükseliş eğilimi oluşturabilir.",
        },
        "HIKE": {
            "overall": "Sıkılaştırıcı",
            "equities": "İskonto oranı ve finansman maliyeti kanalıyla kısa vadede baskı oluşturabilir.",
            "banks": "Fonlama ve kredi talebi etkileri nedeniyle görünüm karmaşık olabilir.",
            "real_estate": "Faiz hassasiyeti yüksek olduğundan göreli baskı görülebilir.",
            "try": "Beklentiyi aşan sıkılaşma Türk lirasını destekleyebilir.",
            "bonds": "Kısa vadeli getiriler yukarı tepki verebilir; güven kanalı sonucu değiştirebilir.",
        },
        "HOLD": {
            "overall": "Nötr / beklentiye bağlı",
            "equities": "Ana etki karar metninin tonu ve piyasa beklentisinden sapmaya bağlıdır.",
            "banks": "Mevcut fonlama koşulları korunur; yönlendirme öne çıkar.",
            "real_estate": "Mevcut sıkılık korunur; belirgin yön için sonraki adım beklentisi izlenir.",
            "try": "Kararın sürprizi ve ileriye dönük yönlendirme belirleyicidir.",
            "bonds": "Faiz patikası beklentisi metindeki tonla yeniden fiyatlanabilir.",
        },
        "SCHEDULED": {
            "overall": "Karar bekleniyor",
            "equities": "Toplantı öncesi beklenti ve oynaklık izlenir.",
            "banks": "Karar bekleniyor.",
            "real_estate": "Karar bekleniyor.",
            "try": "Karar bekleniyor.",
            "bonds": "Karar bekleniyor.",
        },
    }
    return {
        "method": "rule_based_scenario_v1",
        "change_bps": change_bps,
        **scenarios[decision_type],
        "disclaimer": "Senaryo bazlı genel aktarım kanalıdır; gerçekleşmiş getiri veya yatırım tavsiyesi değildir.",
    }


def map_decision(content: str, *, decision_date: date, source_url: str) -> dict:
    parser = DecisionParser()
    parser.feed(content)
    text = "\n".join(parser.blocks)
    decision_no_match = re.search(r"Sayı:\s*(\d{4}-\d+)", text)
    policy_paragraph = next(
        (item for item in parser.blocks if "politika faizi olan" in item.casefold()), ""
    )
    policy_rates = _policy_rates(policy_paragraph)
    lending_rates = _rates_after(
        "borç verme faiz oranını", "gecelik vadede borçlanma", policy_paragraph
    )
    borrowing_rates = _rates_after(
        "borçlanma faiz oranını ise",
        r"(?:sabit tutmuştur|indirmiştir|artırmıştır|yükseltmiştir)",
        policy_paragraph,
    )
    policy_rate = policy_rates[-1] if policy_rates else None
    previous = policy_rates[0] if len(policy_rates) > 1 else None
    lending = lending_rates[-1] if lending_rates else None
    borrowing = borrowing_rates[-1] if borrowing_rates else None
    policy_clause = policy_paragraph.casefold().split("kurul ayrıca", 1)[0]
    if previous is not None and policy_rate is not None and policy_rate < previous:
        decision_type = "CUT"
    elif previous is not None and policy_rate is not None and policy_rate > previous:
        decision_type = "HIKE"
    elif len(policy_rates) == 1 or "sabit tutul" in policy_clause:
        decision_type = "HOLD"
        previous = previous or policy_rate
    elif "indiril" in policy_clause:
        decision_type = "CUT"
    elif "artırıl" in policy_clause or "yükseltil" in policy_clause:
        decision_type = "HIKE"
    else:
        decision_type = "HOLD"
        previous = previous or policy_rate
    change_bps = (
        int((policy_rate - previous) * 100)
        if policy_rate is not None and previous is not None
        else None
    )
    guidance = next(
        (item for item in parser.blocks if "Kurul politika faizine ilişkin" in item), None
    )
    return {
        "decision_no": decision_no_match.group(1) if decision_no_match else f"tcmb:{decision_date}",
        "decision_date": decision_date,
        "status": "PUBLISHED",
        "decision_type": decision_type,
        "policy_rate": policy_rate,
        "previous_policy_rate": previous,
        "change_bps": change_bps,
        "lending_rate": lending,
        "borrowing_rate": borrowing,
        "title": next(
            (item for item in parser.blocks if "Faiz Oranlarına" in item), "PPK Faiz Kararı"
        ),
        "summary": policy_paragraph or None,
        "guidance": guidance,
        "source_url": source_url,
        "raw_text": text,
        "market_impact": build_market_impact(decision_type, change_bps),
    }


class TcmbPolicyCollector(BaseCollector):
    name = "tcmb_policy"

    def __init__(
        self,
        session: AsyncSession,
        *,
        years: list[int] | None = None,
        refresh: bool = False,
    ) -> None:
        super().__init__(rate_limit_per_sec=2)
        self.session = session
        current_year = datetime.now(UTC).year
        self.years = years or [current_year - 2, current_year - 1, current_year]
        self.refresh = refresh

    async def run(self) -> dict:
        rows: dict[date, str | None] = {}
        for year in self.years:
            content = (await self.get_bytes(CALENDAR_URL.format(year=year))).decode(
                "utf-8", "replace"
            )
            rows.update(parse_calendar(content))

        existing_rows = (
            await self.session.execute(
                select(MonetaryPolicyDecision.decision_date, MonetaryPolicyDecision.status).where(
                    MonetaryPolicyDecision.decision_date.in_(rows)
                )
            )
        ).all()
        existing = {item.decision_date: item.status for item in existing_rows}
        fields: list[dict] = []
        for decision_date, source_url in sorted(rows.items()):
            if source_url:
                if existing.get(decision_date) == "PUBLISHED" and not self.refresh:
                    continue
                detail = (await self.get_bytes(source_url)).decode("utf-8", "replace")
                fields.append(
                    map_decision(detail, decision_date=decision_date, source_url=source_url)
                )
            else:
                fields.append(
                    {
                        "decision_no": f"scheduled:{decision_date.isoformat()}",
                        "decision_date": decision_date,
                        "status": "SCHEDULED",
                        "decision_type": "SCHEDULED",
                        "policy_rate": None,
                        "previous_policy_rate": None,
                        "change_bps": None,
                        "lending_rate": None,
                        "borrowing_rate": None,
                        "title": "Planlanan PPK Toplantısı",
                        "summary": None,
                        "guidance": None,
                        "source_url": CALENDAR_URL.format(year=decision_date.year),
                        "raw_text": None,
                        "market_impact": build_market_impact("SCHEDULED", None),
                    }
                )

        for item in fields:
            stmt = pg_insert(MonetaryPolicyDecision).values(**item)
            await self.session.execute(
                stmt.on_conflict_do_update(
                    constraint="uq_monetary_policy_decision_date",
                    set_={
                        **{
                            key: getattr(stmt.excluded, key)
                            for key in item
                            if key != "decision_date"
                        },
                        "updated_at": func.now(),
                    },
                )
            )
        await self.session.commit()
        return {
            "listed": len(rows),
            "published": sum(source_url is not None for source_url in rows.values()),
            "scheduled": sum(source_url is None for source_url in rows.values()),
            "details_fetched": sum(item["status"] == "PUBLISHED" for item in fields),
            "new": len(set(rows) - set(existing)),
        }
