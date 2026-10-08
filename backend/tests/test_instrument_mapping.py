"""KAP sirket listesi -> instrument alan esleme testleri (agsiz, DB'siz)."""

import json
from pathlib import Path

from app.collectors.instruments import map_kap_item_to_instrument_fields

FIXTURE = Path(__file__).parent / "fixtures" / "kap" / "company_items_sample.json"


def _load_items() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_maps_normal_item_correctly():
    items = _load_items()
    acsel = next(i for i in items if i["stockCode"] == "ACSEL")

    rows = map_kap_item_to_instrument_fields(acsel)

    assert len(rows) == 1
    fields = rows[0]
    assert fields["ticker"] == "ACSEL"
    assert fields["kap_member_oid"] == acsel["kapMemberOid"]
    assert fields["mkk_member_oid"] == acsel["mkkMemberOid"]
    assert fields["is_active"] is True
    assert isinstance(fields["name"], str) and len(fields["name"]) > 0


def test_skips_item_without_stock_code():
    item = {"stockCode": "-", "kapMemberOid": "x", "kapMemberTitle": "Bagimsiz Denetim A.S."}
    assert map_kap_item_to_instrument_fields(item) == []

    item2 = {"stockCode": "", "kapMemberOid": "x", "kapMemberTitle": "..."}
    assert map_kap_item_to_instrument_fields(item2) == []

    item3 = {"kapMemberOid": "x", "kapMemberTitle": "..."}  # stockCode alani hic yok
    assert map_kap_item_to_instrument_fields(item3) == []


def test_inactive_member_state_maps_to_false():
    item = {
        "stockCode": "TEST",
        "kapMemberOid": "x",
        "kapMemberTitle": "Test A.S.",
        "kapMemberState": "P",  # pasif
    }
    rows = map_kap_item_to_instrument_fields(item)
    assert rows[0]["is_active"] is False


def test_ticker_is_uppercased_and_stripped():
    item = {"stockCode": " thyao ", "kapMemberOid": "x", "kapMemberTitle": "THY"}
    rows = map_kap_item_to_instrument_fields(item)
    assert rows[0]["ticker"] == "THYAO"


def test_splits_multiple_share_class_tickers():
    item = {
        "stockCode": " KRDMA, KRDMB, KRDMD ",
        "kapMemberOid": "kardemir-oid",
        "kapMemberTitle": "Kardemir",
        "kapMemberState": "A",
    }

    rows = map_kap_item_to_instrument_fields(item)

    assert [row["ticker"] for row in rows] == ["KRDMA", "KRDMB", "KRDMD"]
    assert {row["kap_member_oid"] for row in rows} == {"kardemir-oid"}


def test_all_fixture_items_produce_stable_results():
    """Fixture'daki tum kayitlar hata firlatmadan islensin (regresyon guvenligi)."""
    items = _load_items()
    results = [map_kap_item_to_instrument_fields(i) for i in items]
    rows = [row for item_rows in results for row in item_rows]
    assert len(rows) > 0
    for fields in rows:
        assert fields["ticker"], "bos ticker sizmis olamaz"
        assert fields["kap_member_oid"], "kap_member_oid zorunlu"
