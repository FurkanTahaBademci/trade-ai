"""KAP form metninden olayin kendi tarihini cikaran saf fonksiyonlar.

KAP yapilandirilmis formlari gorunur metne "etiket satiri + deger satiri"
olarak duser (bkz. collectors/kap.html_to_visible_text). Ornekler gercek
yanitlardan alinmistir: tests/fixtures/kap/detail_general_assembly.json ve
detail_dividend.json.

- Genel kurul: "Genel Kurul Tarihi" etiketinin altindaki tarih. Kar payi
  formlarindaki "Konunun Gundemde Yer Aldigi Genel Kurul Tarihi" bilincli
  olarak eslesmez (tam satir karsilastirmasi).
- Kar payi: "Kar Payi Odeme Tarihleri" tablosu. Sutunlar: Odeme sekli |
  Hak kullanim (teklif) | Hak kullanim (kesinlesen) | Odeme | Kayit. Bos
  hucreler metne dusmedigi icin satirda 3 ya da 4 tarih bulunur; olay tarihi
  hak kullanim (paysuz islem) gunudur.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.market_calendar.classifier import EventType, classify_disclosure, fold

_DATE_LINE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")


@dataclass(frozen=True)
class EventDate:
    event_date: date
    detail: str | None = None


def _parse(line: str) -> date | None:
    match = _DATE_LINE.fullmatch(line.strip())
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _general_assembly(lines: list[str]) -> EventDate | None:
    for index, line in enumerate(lines[:-1]):
        if fold(line) == "genel kurul tarihi":
            parsed = _parse(lines[index + 1])
            if parsed:
                return EventDate(parsed)
    return None


def _dividend(lines: list[str]) -> EventDate | None:
    folded = [fold(line) for line in lines]
    try:
        start = folded.index("kar payi odeme tarihleri")
    except ValueError:
        return None
    for index in range(start + 1, len(lines)):
        dates: list[date] = []
        cursor = index + 1
        while cursor < len(lines) and (parsed := _parse(lines[cursor])):
            dates.append(parsed)
            cursor += 1
        if len(dates) == 4:
            ex_date, payment = dates[1], dates[2]
        elif len(dates) == 3:
            ex_date, payment = dates[0], dates[1]
        else:
            continue
        return EventDate(ex_date, f"Hak kullanım {ex_date:%d.%m.%Y} · ödeme {payment:%d.%m.%Y}")
    return None


def extract_event_date(event_type: EventType | None, body_text: str | None) -> EventDate | None:
    if not body_text or event_type is None:
        return None
    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    if event_type == EventType.GENERAL_ASSEMBLY:
        return _general_assembly(lines)
    if event_type == EventType.DIVIDEND:
        return _dividend(lines)
    return None


def disclosure_event_date(
    *,
    title: str | None,
    subject: str | None,
    disclosure_class: str | None,
    body_text: str | None,
) -> EventDate | None:
    classification = classify_disclosure(
        title=title, subject=subject, disclosure_class=disclosure_class
    )
    return extract_event_date(classification.event_type if classification else None, body_text)
