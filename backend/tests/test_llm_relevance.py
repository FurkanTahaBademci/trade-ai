"""Kural tabanli haber on filtresi testleri."""

import pytest

from app.llm.relevance import is_market_relevant


@pytest.mark.parametrize(
    "title",
    [
        "Diyarbakır'da Kültür Yolu Festivali başladı",
        "Galatasaray Şampiyonlar Ligi'nde Sporting'e konuk oluyor",
        "Meteoroloji'den sağanak uyarısı",
        "İstanbul'da trafik kazası: 3 yaralandı",
    ],
)
def test_off_topic_news_is_filtered(title):
    assert not is_market_relevant(title, None, [])


@pytest.mark.parametrize(
    "title",
    [
        "TCMB politika faizini sabit tuttu",
        "İran'ın Hürmüz Boğazı'ndaki tanker saldırıları",
        "Brent petrol 100 doları aştı",
        "Rusya'nın Zaporijya bölgesine saldırısı",  # konu belirsiz -> LLM karar verir
        "Spor kulübü hisseleri borsada yükseldi",  # piyasa terimi kazanir
    ],
)
def test_market_or_ambiguous_news_goes_to_llm(title):
    assert is_market_relevant(title, None, [])


def test_explicit_ticker_always_goes_to_llm():
    assert is_market_relevant("Festival sponsoru oldu", None, ["TTKOM"])


def test_summary_is_also_checked():
    assert is_market_relevant("Konser iptal edildi", "Organizatör şirket zarar açıkladı", [])
