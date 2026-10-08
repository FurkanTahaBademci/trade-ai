from app.core.sectors import resolve_sector


def test_resolve_known_tickers():
    assert resolve_sector("THYAO") == "Havacılık & Ulaştırma"
    assert resolve_sector("AKBNK") == "Bankacılık"
    assert resolve_sector("EREGL") == "Demir Çelik"
    assert resolve_sector("TUPRS") == "Enerji & Petrol"
    assert resolve_sector("EKGYO") == "Gayrimenkul (GYO)"
    assert resolve_sector("ASELS") == "Savunma & Teknoloji"
    assert resolve_sector("BIMAS") == "Perakende & Tüketim"


def test_resolve_keywords_from_name():
    assert resolve_sector("XYZ1", "XYZ ENERJİ ÜRETİM A.Ş.") == "Enerji & Elektrik"
    assert resolve_sector("XYZ2", "XYZ GAYRİMENKUL YATIRIM ORTAKLIĞI") == "Gayrimenkul (GYO)"
    assert resolve_sector("XYZ3", "XYZ ÇİMENTO SANAYİ T.A.Ş.") == "Çimento & Yapı"
    assert resolve_sector("XYZ4", "XYZ YAZILIM VE BİLİŞİM HİZMETLERİ") == "Teknoloji & Yazılım"
    assert resolve_sector("XYZ5", "XYZ HAYAT VE EMEKLİLİK A.Ş.") == "Sigorta & Emeklilik"


def test_resolve_fallback():
    assert resolve_sector("UNKNOWN", "BİLİNMEYEN BİR FİRMA") == "Diğer Sanayi & Hizmet"
