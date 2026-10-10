"""Resmi TCMB takvim/karar parser'i ve etki senaryosu testleri."""

from datetime import date
from pathlib import Path

from app.collectors.tcmb_policy import build_market_impact, map_decision, parse_calendar
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures" / "tcmb_policy"


def test_calendar_parser_reads_published_and_scheduled_decisions():
    rows = parse_calendar((FIXTURES / "calendar_2026.html").read_text(encoding="utf-8"))

    assert rows[0] == (
        date(2026, 1, 22),
        "https://www.tcmb.gov.tr/wps/wcm/connect/tr/tcmb+tr/main+menu/duyurular/basin/2026/duy2026-01",
    )
    assert rows[-2] == (date(2026, 9, 10), None)
    assert rows[-1] == (date(2026, 10, 22), None)


def test_decision_parser_maps_hold_and_corridor_rates():
    result = map_decision(
        (FIXTURES / "decision_2026_28.html").read_text(encoding="utf-8"),
        decision_date=date(2026, 7, 23),
        source_url="https://www.tcmb.gov.tr/example",
    )

    assert result["decision_no"] == "2026-28"
    assert result["decision_type"] == "HOLD"
    assert float(result["policy_rate"]) == 37
    assert float(result["previous_policy_rate"]) == 37
    assert float(result["lending_rate"]) == 40
    assert float(result["borrowing_rate"]) == 35.5
    assert result["change_bps"] == 0


def test_decision_parser_uses_new_rate_for_cut():
    content = """
    <div id="tcmbMainContent"><p>Sayı: 2026-01</p>
    <h2>Faiz Oranlarına İlişkin Basın Duyurusu</h2>
    <p>Para Politikası Kurulu (Kurul), politika faizi olan bir hafta vadeli repo
    ihale faiz oranının yüzde 38’den yüzde 37’ye indirilmesine karar vermiştir.
    Kurul ayrıca, Merkez Bankası gecelik vadede borç verme faiz oranını yüzde
    41’den yüzde 40’a, gecelik vadede borçlanma faiz oranını ise yüzde 36,5’ten
    yüzde 35,5’e indirmiştir.</p></div>
    """

    result = map_decision(
        content,
        decision_date=date(2026, 1, 22),
        source_url="https://www.tcmb.gov.tr/example",
    )

    assert result["decision_type"] == "CUT"
    assert float(result["previous_policy_rate"]) == 38
    assert float(result["policy_rate"]) == 37
    assert result["change_bps"] == -100


def test_corridor_hike_does_not_turn_policy_hold_into_hike():
    content = """
    <div id="tcmbMainContent"><p>Sayı: 2025-20</p>
    <h2>Para Politikası Kurulu Ara Toplantı Kararı</h2>
    <p>Bu doğrultuda Kurul, Merkez Bankası gecelik vadede borç verme faiz oranının
    yüzde 46'ya yükseltilmesine karar vermiştir. Politika faizi olan bir hafta
    vadeli repo ihale faiz oranını yüzde 42,5'te, Merkez Bankası gecelik vadede
    borçlanma faiz oranını ise yüzde 41'de sabit tutmuştur.</p>
    </div>
    """

    result = map_decision(
        content,
        decision_date=date(2025, 3, 20),
        source_url="https://www.tcmb.gov.tr/example",
    )

    assert result["decision_type"] == "HOLD"
    assert float(result["policy_rate"]) == 42.5
    assert result["change_bps"] == 0


def test_market_impact_is_scenario_not_return_claim():
    impact = build_market_impact("HIKE", 250)

    assert impact["overall"] == "Sıkılaştırıcı"
    assert impact["change_bps"] == 250
    assert "yatırım tavsiyesi değildir" in impact["disclaimer"]


def test_macro_route_is_registered():
    assert "/api/macro/policy-decisions" in app.openapi()["paths"]
