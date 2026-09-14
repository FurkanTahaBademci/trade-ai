"""isyatirimhisse satiri -> price_daily alan esleme testleri (agsiz, DB'siz).

Sentetik kayitlar kullaniyoruz ama kolon adlari (HGDG_HS_KODU, HGDG_TARIH, ...)
bu oturumda gercek `fetch_stock_data` cagrisindan dogrulandi — bkz.
.claude/PROGRESS.md Faz 1 notlari.
"""

import math
from datetime import date

import pandas as pd

from app.collectors.prices import map_price_record


def _real_shaped_record(**overrides) -> dict:
    base = {
        "HGDG_HS_KODU": "THYAO",
        "HGDG_TARIH": pd.Timestamp("2026-09-04"),
        "HGDG_KAPANIS": 296.0,
        "HGDG_MAX": 299.0,
        "HGDG_MIN": 292.25,
        "HGDG_AOF": 295.493,
        "HGDG_HACIM": 13238040000.0,
        "DOLAR_BAZLI_FIYAT": 48.3195,
        "PD": 408480000000.0,
        # Kullanilmayan bir kolon de olabilir (kutuphane 30+ kolon donuyor,
        # sadece _COLUMN_MAP'te olanlari aliyoruz):
        "END_ENDEKS_KODU": "01",
    }
    base.update(overrides)
    return base


def test_maps_real_shaped_record_correctly():
    mapped = map_price_record(_real_shaped_record())

    assert mapped is not None
    assert mapped["ticker"] == "THYAO"
    assert mapped["date"] == date(2026, 9, 4)
    assert mapped["close"] == 296.0
    assert mapped["high"] == 299.0
    assert mapped["low"] == 292.25
    assert mapped["avg_price"] == 295.493
    assert mapped["volume_try"] == 13238040000.0
    assert mapped["close_usd"] == 48.3195
    assert mapped["market_cap_try"] == 408480000000.0
    # Esleme sozlugunde olmayan kolonlar ciktiya sizmamali:
    assert "END_ENDEKS_KODU" not in mapped


def test_nan_values_become_none():
    mapped = map_price_record(_real_shaped_record(HGDG_MAX=float("nan"), PD=math.nan))

    assert mapped is not None
    assert mapped["high"] is None
    assert mapped["market_cap_try"] is None


def test_missing_close_is_rejected():
    record = _real_shaped_record(HGDG_KAPANIS=float("nan"))
    assert map_price_record(record) is None


def test_missing_ticker_is_rejected():
    record = _real_shaped_record(HGDG_HS_KODU=None)
    assert map_price_record(record) is None


def test_python_date_input_also_works():
    """Bazi durumlarda tarih zaten datetime.date olabilir (Timestamp degil)."""
    mapped = map_price_record(_real_shaped_record(HGDG_TARIH=date(2026, 1, 15)))
    assert mapped is not None
    assert mapped["date"] == date(2026, 1, 15)


def test_string_date_dmy_format_works():
    """IS Yatirim ham JSON ciktisi gun-ay-yil (03-09-2024) stringi olarak gelir."""
    mapped = map_price_record(_real_shaped_record(HGDG_TARIH="03-09-2024"))
    assert mapped is not None
    assert mapped["date"] == date(2024, 9, 3)


def test_string_date_iso_format_works():
    """ISO formatli tarih stringi (2026-09-04) basariyla date nesnesine donusur."""
    mapped = map_price_record(_real_shaped_record(HGDG_TARIH="2026-09-04"))
    assert mapped is not None
    assert mapped["date"] == date(2026, 9, 4)


def test_price_collector_chunk_size_configuration():
    from unittest.mock import MagicMock
    from app.collectors.prices import PriceCollector

    session = MagicMock()
    collector = PriceCollector(session, chunk_size=7)
    assert collector._chunk_size == 7

    default_collector = PriceCollector(session)
    assert default_collector._chunk_size == 10

