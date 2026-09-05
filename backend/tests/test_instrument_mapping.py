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

    fields = map_kap_item_to_instrument_fields(acsel)

    assert fields is not None
    assert fields["ticker"] == "ACSEL"
    assert fields["kap_member_oid"] == acsel["kapMemberOid"]
    assert fields["mkk_member_oid"] == acsel["mkkMemberOid"]
    assert fields["is_active"] is True
    assert isinstance(fields["name"], str) and len(fields["name"]) > 0


def test_skips_item_without_stock_code():
    item = {"stockCode": "-", "kapMemberOid": "x", "kapMemberTitle": "Bagimsiz Denetim A.S."}
    assert map_kap_item_to_instrument_fields(item) is None

    item2 = {"stockCode": "", "kapMemberOid": "x", "kapMemberTitle": "..."}
    assert map_kap_item_to_instrument_fields(item2) is None

    item3 = {"kapMemberOid": "x", "kapMemberTitle": "..."}  # stockCode alani hic yok
    assert map_kap_item_to_instrument_fields(item3) is None


def test_inactive_member_state_maps_to_false():
    item = {
        "stockCode": "TEST",
        "kapMemberOid": "x",
        "kapMemberTitle": "Test A.S.",
        "kapMemberState": "P",  # pasif
    }
    fields = map_kap_item_to_instrument_fields(item)
    assert fields is not None
    assert fields["is_active"] is False


def test_ticker_is_uppercased_and_stripped():
    item = {"stockCode": " thyao ", "kapMemberOid": "x", "kapMemberTitle": "THY"}
    fields = map_kap_item_to_instrument_fields(item)
    assert fields is not None
    assert fields["ticker"] == "THYAO"


def test_all_fixture_items_produce_stable_results():
    """Fixture'daki tum kayitlar hata firlatmadan islensin (regresyon guvenligi)."""
    items = _load_items()
    results = [map_kap_item_to_instrument_fields(i) for i in items]
    non_null = [r for r in results if r is not None]
    assert len(non_null) > 0
    for fields in non_null:
        assert fields["ticker"], "bos ticker sizmis olamaz"
        assert fields["kap_member_oid"], "kap_member_oid zorunlu"
