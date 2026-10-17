"""KAP bildirim metni temizligi ve KAP test bildirimi tespiti.

Saf fonksiyonlar hem collector'da (ingest) hem API'de (okuma aninda, eski
kayitlar migration'siz duzelsin diye) kullanilir. SQL kosulu liste
endpoint'lerinin ve LLM belge seciminin test bildirimlerini elemesi icindir.
"""

from __future__ import annotations

import re

from sqlalchemy import ColumnElement, String, cast, func, not_, or_

from app.models import KapDisclosure

# KAP form sablonunun alan anahtarlari: `oda_ExplanationTextBlock|`,
# `oda_EmptyField|` gibi. Gorunur metinde degil, gizlenmemis bir hucrede
# gelir; kullaniciya hicbir anlam tasimaz.
_TEMPLATE_KEY_RE = re.compile(r"^[a-z]{2,8}_[A-Za-z0-9_]+\|?$")
# Iki dilli formlarda deger "Hayır (No)" bicimindedir; Turkce kismi yeterli.
_BILINGUAL_VALUE_RE = re.compile(r"^(Evet|Hayır)\s*\((Yes|No)\)$")
_EMPTY_VALUES = frozenset({"[]", "[ ]"})
# Deger hucresi bos/`[]` geldiginde tek basina anlamsiz kalan bas etiketler.
_OPTIONAL_HEADER_LABELS = frozenset({"İlgili Şirketler", "İlgili Fonlar"})
# Form tablosunun dil sutunu basligi; yalniz sablon anahtarindan hemen once
# geldiginde (eski, temizlenmemis kayitlarda) atilir, deger olarak dokunulmaz.
_LANGUAGE_HEADERS = frozenset({"Türkçe", "İngilizce"})

KAP_TEST_TICKERS = frozenset({"KTEST"})
KAP_TEST_COMPANY_TITLES = frozenset({"KAP TEST A.Ş."})
# Baslik/ozet alaninin tamami bu ifadeyse bildirim KAP'in sistem testidir.
KAP_TEST_HEADLINES = frozenset({"test bildirimi"})
# Govdede gecen sabit uyari cumlesi (KAP "dikkate almayiniz" ASCII yazar).
KAP_TEST_BODY_PHRASES = ("test bildirimidir, dikkate almay",)


def _fold(value: str) -> str:
    """Turkce I/ı farkini ve son noktalama isaretlerini yok sayan kucuk harf."""
    folded = re.sub("[İIı]", "i", value).lower()
    return re.sub(r"\s+", " ", folded).strip(" .!")


def clean_kap_body_text(text: str | None) -> str | None:
    """KAP gorunur metninden sablon artiklarini ayiklayan saf fonksiyon.

    Atilanlar: `oda_*|` alan anahtarlari, `[]` bos degerleri, bos degerli
    "İlgili Şirketler/Fonlar" etiketleri ve anahtarlardan once gelen dil sutunu
    basligi. "Hayır (No)" -> "Hayır". Icerik satirlari ve sirasi korunur.
    """
    if text is None:
        return None
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    kept: list[str] = []
    for position, line in enumerate(lines):
        if _TEMPLATE_KEY_RE.match(line) or line in _EMPTY_VALUES:
            continue
        following = lines[position + 1] if position + 1 < len(lines) else None
        if line in _LANGUAGE_HEADERS and following and _TEMPLATE_KEY_RE.match(following):
            continue
        if line in _OPTIONAL_HEADER_LABELS and (
            following is None
            or following in _EMPTY_VALUES
            or following in _OPTIONAL_HEADER_LABELS
            or following in _LANGUAGE_HEADERS
        ):
            continue
        bilingual = _BILINGUAL_VALUE_RE.match(line)
        kept.append(bilingual.group(1) if bilingual else line)
    return "\n".join(kept) or None


def is_kap_test_disclosure(
    *,
    ticker_codes: list[str] | None = None,
    kap_title: str | None = None,
    subject: str | None = None,
    summary: str | None = None,
    body_text: str | None = None,
) -> bool:
    """KAP'in kendi sistem test bildirimlerini tanir (KTEST, "Test Bildirimi").

    Tutucu kural: yalniz test sirketi/ticker'i, basligin ya da ozetin TAMAMEN
    "Test bildirimi" olmasi veya govdedeki sabit "dikkate almayiniz" uyarisi
    eslesir; icinde "test" gecen gercek bildirimler (orn. "test sureci") elenmez.
    """
    if any(code.upper() in KAP_TEST_TICKERS for code in ticker_codes or []):
        return True
    if kap_title and kap_title.strip().upper() in KAP_TEST_COMPANY_TITLES:
        return True
    if any(value and _fold(value) in KAP_TEST_HEADLINES for value in (subject, summary)):
        return True
    if body_text:
        folded_body = _fold(body_text)
        return any(phrase in folded_body for phrase in KAP_TEST_BODY_PHRASES)
    return False


def kap_test_disclosure_clause(*, include_body: bool = False) -> ColumnElement[bool]:
    """`is_kap_test_disclosure` kuralinin tasinabilir SQL karsiligi.

    Yalniz PostgreSQL ve SQLite'ta ortak fonksiyonlar kullanilir. KAP'in
    gozlenen yazimlari ("Test bildirimi", "Test Bildirimi") kucuk harfe
    indirgenerek eslesir; Python kurali (detay/ingest) daha genistir. Liste
    sorgulari govdeyi okumamak icin varsayilan olarak yalniz metadata
    kolonlarina bakar; govdeyi zaten okuyan LLM secimi `include_body=True` verir.
    """
    headlines = sorted(
        {variant for value in KAP_TEST_HEADLINES for variant in (value, f"{value}.")}
    )
    conditions: list[ColumnElement[bool]] = [
        # JSON dizisinin metin hali (`["KTEST"]`) her iki veritabaninda da ayni.
        cast(KapDisclosure.ticker_codes, String).like(f'%"{ticker}"%')
        for ticker in sorted(KAP_TEST_TICKERS)
    ]
    conditions.append(
        func.upper(func.trim(KapDisclosure.kap_title)).in_(sorted(KAP_TEST_COMPANY_TITLES))
    )
    conditions.append(func.lower(func.trim(KapDisclosure.subject)).in_(headlines))
    conditions.append(func.lower(func.trim(KapDisclosure.summary)).in_(headlines))
    if include_body:
        conditions.extend(
            KapDisclosure.body_text.ilike(f"%{phrase}%") for phrase in KAP_TEST_BODY_PHRASES
        )
    return or_(*conditions)


def not_kap_test_disclosure(*, include_body: bool = False) -> ColumnElement[bool]:
    """Test bildirimlerini disarida birakan WHERE kosulu (NULL-guvenli)."""
    return not_(func.coalesce(kap_test_disclosure_clause(include_body=include_body), False))
