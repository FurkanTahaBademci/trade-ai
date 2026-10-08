"""KAP liste/detay/ek parser testleri (agsiz ve DB'siz)."""

import json
import struct
from datetime import datetime
from pathlib import Path

import pytest

from app.collectors.base import CollectorError
from app.collectors.kap import (
    map_attachment_metadata,
    map_disclosure_detail,
    map_disclosure_list_item,
    parse_kap_datetime,
    parse_ticker_codes,
    unwrap_java_serialized_byte_array,
)

FIXTURES = Path(__file__).parent / "fixtures" / "kap"
JAVA_BYTE_ARRAY_PREFIX = bytes.fromhex("aced0005757200025b42acf317f8060854e00200007870")


def _load(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_maps_real_disclosure_list_item():
    item = _load("disclosure_list_sample.json")[0]

    mapped = map_disclosure_list_item(item)

    assert mapped["disclosure_index"] == 1659260
    assert mapped["published_at"] == datetime.fromisoformat("2026-09-05T19:46:23+03:00")
    assert mapped["ticker_codes"] == ["TSK", "TSKB"]
    assert mapped["summary"] == "IBRD ile imzalanan kredi sözleşmesi hk."
    assert mapped["disclosure_class"] == "ODA"
    assert mapped["has_multi_language_support"] is True
    assert mapped["raw_list_item"] == item


def test_list_item_requires_stable_identity_and_date():
    with pytest.raises(CollectorError, match="disclosureIndex/publishDate eksik"):
        map_disclosure_list_item({"kapTitle": "eksik"})


def test_both_kap_datetime_formats_are_supported():
    list_date = parse_kap_datetime("05.09.2026 19:46:23")
    detail_date = parse_kap_datetime("2026.09.05 19:46:23")
    assert list_date == detail_date
    assert list_date.utcoffset().total_seconds() == 3 * 60 * 60


def test_ticker_codes_are_normalized_and_deduplicated():
    assert parse_ticker_codes(" thyao, ASELS;THYAO / garan ") == [
        "THYAO",
        "ASELS",
        "GARAN",
    ]
    assert parse_ticker_codes(None) == []


def test_maps_real_detail_and_extracts_only_visible_language():
    payload = _load("disclosure_detail_sample.json")

    mapped = map_disclosure_detail(payload)

    assert mapped["body_html"].startswith("<table")
    assert "200 milyon Avro" in mapped["body_text"]
    assert "Accelerating the Market Transition" not in mapped["body_text"]
    assert mapped["attachments"] == []
    assert mapped["raw_detail"] == payload[0]


def test_maps_verified_attachment_metadata_shape():
    # 1659248 numarali gercek KAP detayindan 2026-09-06 tarihinde dogrulanan
    # alanlar; buyuk HTML govdesini ikinci kez fixture'a kopyalamiyoruz.
    item = {
        "objId": "4028328d9f52dddd01a06d943dc11178",
        "fileName": "SPK Onaylı  Pay Satış Bilgi Formu.pdf",
        "fileExtension": "pdf",
    }

    mapped = map_attachment_metadata(1659248, item)

    assert mapped["obj_id"] == item["objId"]
    assert mapped["disclosure_index"] == 1659248
    assert mapped["file_name"].endswith(".pdf")
    assert mapped["file_extension"] == "pdf"
    assert mapped["raw_metadata"] == item


def test_unwraps_java_serialized_byte_array():
    pdf = b"%PDF-1.4\nsmall-test"
    wrapped = JAVA_BYTE_ARRAY_PREFIX + struct.pack(">i", len(pdf)) + pdf

    assert unwrap_java_serialized_byte_array(wrapped) == pdf


def test_raw_file_is_forward_compatible():
    pdf = b"%PDF-1.7\nfuture-raw-response"
    assert unwrap_java_serialized_byte_array(pdf) == pdf


def test_rejects_truncated_or_unknown_java_payload():
    wrapped = JAVA_BYTE_ARRAY_PREFIX + struct.pack(">i", 100) + b"short"
    with pytest.raises(CollectorError, match="uzunluk uyusmazligi"):
        unwrap_java_serialized_byte_array(wrapped)

    with pytest.raises(CollectorError, match=r"byte\[\] semasi taninmadi"):
        unwrap_java_serialized_byte_array(b"\xac\xed\x00\x05not-byte-array")
