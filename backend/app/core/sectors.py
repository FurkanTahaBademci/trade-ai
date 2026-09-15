"""BIST hisseleri icin sektor esleme ve siniflandirma yardimcisi."""

from __future__ import annotations

# BIST 100 ve en likit hisseler icin kesin sektor haritasi
KNOWN_TICKER_SECTORS: dict[str, str] = {
    # Bankacılık & Finans
    "AKBNK": "Bankacılık", "GARAN": "Bankacılık", "ISCTR": "Bankacılık",
    "YKBNK": "Bankacılık", "VAKBN": "Bankacılık", "HALKB": "Bankacılık",
    "TSKB": "Bankacılık", "ALBRK": "Bankacılık", "SKBNK": "Bankacılık",
    "QNBFB": "Bankacılık", "ICBCT": "Bankacılık", "KLNMA": "Bankacılık",
    "SEKFK": "Finansal Hizmetler", "VAKFN": "Finansal Hizmetler", "ISFIN": "Finansal Hizmetler",
    "GARFA": "Finansal Hizmetler", "QNBFL": "Finansal Hizmetler", "CRDFA": "Finansal Hizmetler",
    "INFO": "Finansal Hizmetler", "OSMEN": "Finansal Hizmetler", "GEDIK": "Finansal Hizmetler",
    "ISMEN": "Finansal Hizmetler", "GLBMD": "Finansal Hizmetler", "OYYAT": "Finansal Hizmetler",

    # Havacılık & Ulaştırma & Lojistik
    "THYAO": "Havacılık & Ulaştırma", "PGSUS": "Havacılık & Ulaştırma",
    "TAVHL": "Havacılık & Ulaştırma", "CLEBI": "Havacılık & Ulaştırma",
    "RYSAS": "Lojistik & Taşımacılık", "GSDHO": "Lojistik & Taşımacılık",
    "TLMAN": "Lojistik & Taşımacılık", "LKMNH": "Sağlık & Hizmet",
    "TMSN": "Otomotiv & Makine", "BEYAZ": "Otomotiv & Makine",

    # Holding & Yatırım
    "KCHOL": "Holding & Yatırım", "SAHOL": "Holding & Yatırım",
    "SISE": "Cam & Sanayi", "AGHOL": "Holding & Yatırım",
    "DOHOL": "Holding & Yatırım", "ALARK": "Holding & Yatırım",
    "TKFEN": "Holding & İnşaat", "ENKAI": "Holding & İnşaat",
    "BERA": "Holding & Yatırım", "GLYHO": "Holding & Yatırım",
    "VERUS": "Holding & Yatırım", "GZNMI": "Turizm & Seyahat",

    # Enerji, Petrol & Gaz
    "TUPRS": "Enerji & Petrol", "PETKM": "Kimya & Petrol",
    "ASTOR": "Enerji & Elektrik", "EUPWR": "Enerji & Elektrik",
    "CWENE": "Enerji & Elektrik", "SMRTG": "Enerji & Elektrik",
    "GESAN": "Enerji & Elektrik", "ALFAS": "Enerji & Elektrik",
    "GWIND": "Enerji & Elektrik", "AKSEN": "Enerji & Elektrik",
    "ZOREN": "Enerji & Elektrik", "AYDEM": "Enerji & Elektrik",
    "ENJSA": "Enerji & Dağıtım", "ODAS": "Enerji & Madencilik",
    "CANTE": "Enerji & Madencilik", "AHGAZ": "Enerji & Dağıtım",
    "AKFYE": "Enerji & Elektrik", "BIOEN": "Enerji & Elektrik",
    "CONSE": "Enerji & Elektrik", "MAGEN": "Enerji & Elektrik",

    # Otomotiv & Yan Sanayi
    "FROTO": "Otomotiv", "TOASO": "Otomotiv", "TTRAK": "Otomotiv",
    "DOAS": "Otomotiv", "OTKAR": "Otomotiv", "ASUZU": "Otomotiv",
    "KARTN": "Ambalaj & Kağıt", "BFREN": "Otomotiv Yan Sanayi",
    "EGEEN": "Otomotiv Yan Sanayi", "BRISA": "Otomotiv Yan Sanayi",
    "DITAŞ": "Otomotiv Yan Sanayi", "PARSN": "Otomotiv Yan Sanayi",

    # Demir Çelik & Metal
    "EREGL": "Demir Çelik", "KRDMD": "Demir Çelik", "KRDMA": "Demir Çelik",
    "KRDMB": "Demir Çelik", "ISDMR": "Demir Çelik", "CEMTS": "Demir Çelik",
    "BRSAN": "Demir Çelik & Boru", "ERBOS": "Demir Çelik & Boru",
    "BMSCH": "Demir Çelik", "KCAER": "Demir Çelik", "TUCLK": "Demir Çelik",
    "SARKY": "Metal & Bakır",

    # Telekomünikasyon & Teknoloji
    "TCELL": "Telekomünikasyon", "TTKOM": "Telekomünikasyon",
    "ASELS": "Savunma & Teknoloji", "MIATK": "Teknoloji & Yazılım",
    "REEDR": "Teknoloji & Elektronik", "SDTTR": "Savunma & Teknoloji",
    "KONTR": "Teknoloji & Mühendislik", "VBTYZ": "Teknoloji & Yazılım",
    "NETAS": "Telekom & Teknoloji", "LOGO": "Teknoloji & Yazılım",
    "ARDYZ": "Teknoloji & Yazılım", "FONET": "Teknoloji & Sağlık",
    "MOBTL": "Telekom & Bilişim", "INDES": "Bilişim & Dağıtım",
    "PENTA": "Bilişim & Dağıtım", "PAPIL": "Teknoloji & Güvenlik",

    # Perakende, Gıda & Tüketim
    "BIMAS": "Perakende & Tüketim", "MGROS": "Perakende & Tüketim",
    "SOKM": "Perakende & Tüketim", "ULKER": "Gıda & İçecek",
    "CCOLA": "Gıda & İçecek", "AEFES": "Gıda & İçecek",
    "MAVI": "Tekstil & Giyim", "VAKKO": "Tekstil & Lüks Giyim",
    "SUWEN": "Tekstil & Giyim", "TATGD": "Gıda & Tarım",
    "KNFRT": "Gıda & Meyve Suyu", "PETUN": "Gıda & Et",
    "PINSU": "Gıda & Su", "BANVT": "Gıda & Tavukçuluk",
    "YAYLA": "Gıda & Bakliyat", "SOKE": "Gıda & Un",
    "ATAKP": "Gıda & Restoran", "TABGD": "Gıda & Restoran",
    "TETMT": "Gıda & Etiket",

    # Gayrimenkul Yatırım Ortaklığı (GYO)
    "EKGYO": "Gayrimenkul (GYO)", "TRGYO": "Gayrimenkul (GYO)",
    "ISGYO": "Gayrimenkul (GYO)", "SNGYO": "Gayrimenkul (GYO)",
    "VKGYO": "Gayrimenkul (GYO)", "KLGYO": "Gayrimenkul (GYO)",
    "KZGYO": "Gayrimenkul (GYO)", "AVPGY": "Gayrimenkul (GYO)",
    "SURGY": "Gayrimenkul (GYO)", "OZKGY": "Gayrimenkul (GYO)",
    "TORUN": "Gayrimenkul (GYO)", "ALGYO": "Gayrimenkul (GYO)",
    "AKFGY": "Gayrimenkul (GYO)", "HLGYO": "Gayrimenkul (GYO)",
    "DGGYO": "Gayrimenkul (GYO)", "KGYO": "Gayrimenkul (GYO)",

    # Çimento, Yapı Malzemeleri & Maden
    "CIMSA": "Çimento & Yapı", "OYAKC": "Çimento & Yapı",
    "AKCNS": "Çimento & Yapı", "BUCIM": "Çimento & Yapı",
    "AFYON": "Çimento & Yapı", "KLKIM": "Yapı Kimyasalları",
    "KUTPO": "Seramik & Porselen", "USAK": "Seramik & Yapı",
    "EGSER": "Seramik & Yapı", "KOZAL": "Madencilik & Altın",
    "KOZAA": "Madencilik & Altın", "IPEKE": "Madencilik & Enerji",

    # Kimya, İlaç & Sağlık
    "SASA": "Kimya & Elyaf", "HEKTS": "Tarım & Kimya",
    "GUBRF": "Tarım & Gübre", "BAGFS": "Tarım & Gübre",
    "MPARK": "Sağlık & Hastane", "SELEC": "İlaç & Dağıtım",
    "DEVA": "İlaç & Sağlık", "GENIL": "İlaç & Biyoteknoloji",
    "TRILC": "İlaç & Aşı", "RTALB": "Biyoteknoloji & Tanı",
    "KORDS": "Kimya & Kompozit",

    # Sigorta & Emeklilik
    "AGESA": "Sigorta & Emeklilik", "ANSGR": "Sigorta",
    "TURSG": "Sigorta", "AKGRT": "Sigorta", "ANHYT": "Sigorta & Emeklilik",
}

SECTOR_KEYWORDS: list[tuple[str, str]] = [
    ("GYO", "Gayrimenkul (GYO)"),
    ("GAYRIMENKUL", "Gayrimenkul (GYO)"),
    ("GAYRİMENKUL", "Gayrimenkul (GYO)"),
    ("BANKA", "Bankacılık"),
    ("BANKASI", "Bankacılık"),
    ("FAKTORING", "Finansal Hizmetler"),
    ("FAKTORİNG", "Finansal Hizmetler"),
    ("FINANSAL", "Finansal Hizmetler"),
    ("FİNANSAL", "Finansal Hizmetler"),
    ("MENKUL", "Finansal Hizmetler"),
    ("VARLIK", "Finansal Hizmetler"),
    ("SIGORTA", "Sigorta & Emeklilik"),
    ("SİGORTA", "Sigorta & Emeklilik"),
    ("EMEKLILIK", "Sigorta & Emeklilik"),
    ("EMEKLİLİK", "Sigorta & Emeklilik"),
    ("ENERJI", "Enerji & Elektrik"),
    ("ENERJİ", "Enerji & Elektrik"),
    ("ELEKTRIK", "Enerji & Elektrik"),
    ("ELEKTRİK", "Enerji & Elektrik"),
    ("PETROL", "Enerji & Petrol"),
    ("GAZ", "Enerji & Petrol"),
    ("HAVACILIK", "Havacılık & Ulaştırma"),
    ("HAVA", "Havacılık & Ulaştırma"),
    ("LOJISTIK", "Lojistik & Taşımacılık"),
    ("LOJİSTİK", "Lojistik & Taşımacılık"),
    ("TASIMACILIK", "Lojistik & Taşımacılık"),
    ("TAŞIMACILIK", "Lojistik & Taşımacılık"),
    ("HOLDING", "Holding & Yatırım"),
    ("HOLDİNG", "Holding & Yatırım"),
    ("YATIRIM", "Holding & Yatırım"),
    ("YAZILIM", "Teknoloji & Yazılım"),
    ("BILISIM", "Teknoloji & Yazılım"),
    ("BİLİŞİM", "Teknoloji & Yazılım"),
    ("TEKNOLOJI", "Teknoloji & Yazılım"),
    ("TEKNOLOJİ", "Teknoloji & Yazılım"),
    ("SAVUNMA", "Savunma & Sanayi"),
    ("OTOMOTIV", "Otomotiv"),
    ("OTOMOTİV", "Otomotiv"),
    ("MOTOR", "Otomotiv"),
    ("CELIK", "Demir Çelik"),
    ("ÇELİK", "Demir Çelik"),
    ("DEMIR", "Demir Çelik"),
    ("DEMİR", "Demir Çelik"),
    ("METAL", "Metal & Sanayi"),
    ("CIMENTO", "Çimento & Yapı"),
    ("ÇİMENTO", "Çimento & Yapı"),
    ("SERAMIK", "Çimento & Yapı"),
    ("SERAMİK", "Çimento & Yapı"),
    ("MADEN", "Madencilik"),
    ("KIMYA", "Kimya & Sanayi"),
    ("KİMYA", "Kimya & Sanayi"),
    ("PLASTIK", "Kimya & Sanayi"),
    ("PLASTİK", "Kimya & Sanayi"),
    ("ILAC", "İlaç & Sağlık"),
    ("İLAÇ", "İlaç & Sağlık"),
    ("SAGLIK", "İlaç & Sağlık"),
    ("SAĞLIK", "İlaç & Sağlık"),
    ("GIDA", "Gıda & Tüketim"),
    ("TARIM", "Gıda & Tüketim"),
    ("UN", "Gıda & Tüketim"),
    ("SEKER", "Gıda & Tüketim"),
    ("ŞEKER", "Gıda & Tüketim"),
    ("SUT", "Gıda & Tüketim"),
    ("SÜT", "Gıda & Tüketim"),
    ("TEKSTIL", "Tekstil & Deri"),
    ("TEKSTİL", "Tekstil & Deri"),
    ("GIYIM", "Tekstil & Deri"),
    ("GİYİM", "Tekstil & Deri"),
    ("MAGAZA", "Perakende & Tüketim"),
    ("MAĞAZA", "Perakende & Tüketim"),
    ("PERAKENDE", "Perakende & Tüketim"),
    ("ILETISIM", "Telekomünikasyon"),
    ("İLETİŞİM", "Telekomünikasyon"),
    ("TELEKOM", "Telekomünikasyon"),
    ("TURIZM", "Turizm & Seyahat"),
    ("TURİZM", "Turizm & Seyahat"),
    ("INSAAT", "İnşaat & Yapı"),
    ("İNŞAAT", "İnşaat & Yapı"),
]


def resolve_sector(ticker: str, name: str | None = None) -> str:
    """Verilen BIST hissesi icin standart sektor adini dondurur."""
    cleaned_ticker = ticker.strip().upper()
    if cleaned_ticker in KNOWN_TICKER_SECTORS:
        return KNOWN_TICKER_SECTORS[cleaned_ticker]

    if name:
        normalized_name = name.upper().replace("İ", "I").replace("Ü", "U").replace("Ö", "O").replace("Ş", "S").replace("Ğ", "G").replace("Ç", "C")
        raw_upper = name.upper()
        for kw, sector in SECTOR_KEYWORDS:
            if kw in raw_upper or kw in normalized_name:
                return sector

    return "Diğer Sanayi & Hizmet"
