"""Fixture saglik testleri.

Bu testler agdaki servislere baglanmaz — sadece tests/fixtures/ altina
kaydedilmis gercek yanit orneklerinin beklenen sekli koruduğunu dogrular.
Kaynak semasi degisirse (KAP/TEFAS yeni alan eklerse/kaldirirsa) bu testler
kirilir ve haberin olur — bkz. tests/fixtures/README.md.
"""

import json
from pathlib import Path

import feedparser

FIXTURES = Path(__file__).parent / "fixtures"


def test_kap_disclosure_list_shape():
    data = json.loads((FIXTURES / "kap" / "disclosure_list_sample.json").read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) > 0
    first = data[0]
    for key in ("publishDate", "kapTitle", "disclosureClass", "disclosureIndex"):
        assert key in first, f"beklenen alan eksik: {key}"


def test_kap_disclosure_detail_shape():
    data = json.loads((FIXTURES / "kap" / "disclosure_detail_sample.json").read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) > 0
    first = data[0]
    for key in ("disclosure", "disclosureBody", "attachments"):
        assert key in first, f"beklenen alan eksik: {key}"


def test_tefas_dagilim_shape():
    data = json.loads((FIXTURES / "tefas" / "dagilim_sample.json").read_text(encoding="utf-8"))
    assert data.get("errorCode") is None
    rows = data.get("resultList")
    assert isinstance(rows, list)
    assert len(rows) > 0
    for key in ("fonKodu", "fonUnvan", "tarih"):
        assert key in rows[0], f"beklenen alan eksik: {key}"


def test_rss_feeds_parse():
    for name in ("bloomberght", "investing_tr", "aa_ekonomi", "dunya", "foreks", "trthaber"):
        xml_bytes = (FIXTURES / "rss" / f"{name}_sample.xml").read_bytes()
        parsed = feedparser.parse(xml_bytes)
        assert len(parsed.entries) > 0, f"{name} feed'inde entry bulunamadi"
        assert "title" in parsed.entries[0]
        assert "link" in parsed.entries[0]
