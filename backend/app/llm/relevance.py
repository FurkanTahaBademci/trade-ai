"""LLM'e gondermeden once ucuz, kural tabanli haber on filtresi.

Amac piyasayla ilgisi olmayan haberler (spor, kultur-sanat, hava durumu,
asayis) icin Gemini token'i harcamamak. Filtre bilincli olarak tutucudur:
bir haber yalnizca "piyasa disi" bir konu sinyali tasiyor VE hicbir piyasa
sinyali (ticker, finans/ekonomi terimi) tasimiyorsa elenir. Emin olunamayan
her haber LLM'e gider.
"""

from __future__ import annotations

import re

# Turkce buyuk/kucuk harf donusumu: "İ".lower() Python'da "i̇" uretir.
_TR_LOWER = str.maketrans({"İ": "i", "I": "ı"})

_OFF_TOPIC_TERMS = (
    "festival",
    "konser",
    "sergi",
    "tiyatro",
    "sinema",
    "dizi",
    "film",
    "magazin",
    "ünlü",
    "maç",
    "futbol",
    "basketbol",
    "voleybol",
    "şampiyonlar ligi",
    "süper lig",
    "milli takım",
    "teknik direktör",
    "transfer",
    "olimpiyat",
    "hava durumu",
    "meteoroloji",
    "sağanak",
    "kar yağışı",
    "trafik kazası",
    "cinayet",
    "gözaltı",
    "tutuklandı",
    "yangın",
    "kayıp",
    "hayatını kaybetti",
    "yaralandı",
)

_MARKET_TERMS = (
    "borsa",
    "bist",
    "hisse",
    "pay ",
    "şirket",
    "piyasa",
    "yatırım",
    "faiz",
    "enflasyon",
    "tüfe",
    "dolar",
    "euro",
    "kur",
    "tcmb",
    "merkez bankası",
    "fed",
    "ecb",
    "tahvil",
    "eurobond",
    "cds",
    "rezerv",
    "cari açık",
    "bütçe",
    "vergi",
    "ötv",
    "kdv",
    "zam",
    "fiyat",
    "petrol",
    "brent",
    "doğalgaz",
    "altın",
    "emtia",
    "ihracat",
    "ithalat",
    "büyüme",
    "gsyh",
    "işsizlik",
    "sanayi",
    "üretim",
    "banka",
    "kredi",
    "mevduat",
    "sermaye",
    "temettü",
    "bilanço",
    "kâr",
    "zarar",
    "ciro",
    "satış",
    "ihale",
    "sözleşme",
    "halka arz",
    "spk",
    "kap",
    "konkordato",
    "iflas",
    "fon",
    "ekonomi",
    "ticaret",
    "gümrük",
    "yaptırım",
    "tarife",
    "opec",
    "hürmüz",
    "tanker",
    "enerji",
    "elektrik",
    "maden",
    "turizm",
    "otomotiv",
    "havayolu",
)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(term)}", text) for term in terms)


def is_market_relevant(
    title: str | None, summary: str | None, ticker_codes: list[str] | None
) -> bool:
    if ticker_codes:
        return True
    text = f"{title or ''} {summary or ''}".translate(_TR_LOWER).lower()
    if _contains_any(text, _MARKET_TERMS):
        return True
    return not _contains_any(text, _OFF_TOPIC_TERMS)
