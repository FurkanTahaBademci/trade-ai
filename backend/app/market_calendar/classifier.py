"""KAP bildirimlerini takvim olay turlerine ayiran saf, kural tabanli siniflandirici.

LLM kullanmaz; yalnizca `disclosure_class`, baslik ve konu alanlarina bakar.
Turkce buyuk/kucuk harf ve aksan farklari katlanarak karsilastirilir.
"""

from dataclasses import dataclass
from enum import StrEnum


class EventType(StrEnum):
    PPK = "PPK"
    FINANCIAL_REPORT = "FINANCIAL_REPORT"
    DIVIDEND = "DIVIDEND"
    GENERAL_ASSEMBLY = "GENERAL_ASSEMBLY"
    CAPITAL_INCREASE = "CAPITAL_INCREASE"


EVENT_LABELS: dict[EventType, str] = {
    EventType.PPK: "TCMB PPK",
    EventType.FINANCIAL_REPORT: "Finansal rapor",
    EventType.DIVIDEND: "Temettü / kâr payı",
    EventType.GENERAL_ASSEMBLY: "Genel kurul",
    EventType.CAPITAL_INCREASE: "Sermaye artırımı",
}

# PostgreSQL ILIKE on-filtresi icin ASCII-guvenli govde parcalari (bkz. calendar router).
KAP_PREFILTER_STEMS = (
    "finansal rapor",
    "kar pay",
    "kâr pay",
    "temett",
    "genel kurul",
    "sermaye art",
    "bedelsiz",
    "bedelli",
)

_FOLD = str.maketrans(
    {
        "İ": "i",
        "I": "i",
        "ı": "i",
        "Ş": "s",
        "ş": "s",
        "Ğ": "g",
        "ğ": "g",
        "Ü": "u",
        "ü": "u",
        "Ö": "o",
        "ö": "o",
        "Ç": "c",
        "ç": "c",
        "Â": "a",
        "â": "a",
        "Î": "i",
        "î": "i",
        "Û": "u",
        "û": "u",
    }
)


def fold(text: str | None) -> str:
    return " ".join((text or "").translate(_FOLD).lower().split())


@dataclass(frozen=True)
class Classification:
    event_type: EventType
    detail: str | None = None


def classify_disclosure(
    *,
    title: str | None,
    subject: str | None = None,
    disclosure_class: str | None = None,
) -> Classification | None:
    """Bildirim takvim olayi degilse `None` doner."""
    text = fold(f"{title or ''} {subject or ''}")

    if "sermaye art" in text or "bedelsiz" in text or "bedelli" in text:
        if "bedelsiz" in text:
            return Classification(EventType.CAPITAL_INCREASE, "Bedelsiz")
        if "bedelli" in text:
            return Classification(EventType.CAPITAL_INCREASE, "Bedelli")
        return Classification(EventType.CAPITAL_INCREASE)
    if "kar pay" in text or "temett" in text:
        return Classification(EventType.DIVIDEND)
    if "genel kurul" in text:
        return Classification(EventType.GENERAL_ASSEMBLY)
    if "finansal rapor" in text or "bilanco" in text or (disclosure_class or "").upper() == "FR":
        return Classification(EventType.FINANCIAL_REPORT)
    return None
