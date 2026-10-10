# Değişiklik Günlüğü

Bu projedeki önemli değişiklikler bu dosyada tutulur. Biçim
[Keep a Changelog](https://keepachangelog.com/tr-TR/1.1.0/) yapısını, sürüm
numaraları [Semantic Versioning](https://semver.org/lang/tr/) kurallarını izler.

Yeni değişiklikleri `[Unreleased]` başlığının altına yazın; `make release`
bu bölümü yeni sürüm numarasıyla kapatır.

## [Unreleased]

## [0.2.0] - 2026-10-10

### Eklendi

- `/makro` sayfasında TCMB EVDS'den USD/TRY, EUR/TRY gösterge kurları ve TÜFE
  (yıllık değişimle). Yeni isteğe bağlı ayar: `EVDS_API_KEY`; tanımlı değilse
  toplayıcı çalışmaz ve kartlar görünmez.
- İzleme listesi yönetici girişliyken sunucuya senkronlanır ve Telegram/webhook
  bildirimleri bu listedeki hisselerin etiket değişimlerini de izler.
  Ziyaretçilerde liste yalnız tarayıcıda kalır.
- Piyasalar hisse listesinde son fiyat, günlük değişim, işlem hacmi, sektör ve
  bileşik skor sütunları; değişim, hacim veya skora göre sıralama. Skoru
  olmayan hisseler "50 / Nötr" yerine "—" gösterir.
- Takvimde genel kurullar toplantı gününe, temettüler hak kullanım (paysuz
  işlem) gününe yerleşir; ödeme tarihi detayda gösterilir. Tarihler KAP form
  metninden toplama sırasında çıkarılır. Eski bildirimler için:
  `python -m scripts.run_once kap-event-dates`.
- Yönetim ekranları için `/giris` giriş sayfası: imzalı ve 12 saat geçerli
  oturum çerezi, `/sistem` ve `/backtest` başlıklarında "Çıkış yap" düğmesi,
  hatalı denemelere karşı kilit. Giriş sonrası açılmak istenen sayfaya dönülür.

### Değişti

- Tarayıcının HTTP Basic Auth penceresi kaldırıldı. Mevcut
  `WEB_ADMIN_USERNAME` / `WEB_ADMIN_PASSWORD` ayarları aynen kullanılır; yeni
  ayar gerekmez. Parola değiştirildiğinde tüm açık oturumlar kapanır.
- Paper portföy işlem gerekçeleri Türkçe ve okunur biçimde yazılır
  ("Bileşik skor 87,5 ≥ 75; güven %35"). Eski işlemler değişmez.
- **Bileşik skor modeli v3.** v1 geçmişi veritabanında kalır; ekranlar,
  paper portföy, backtest ve bildirimler v3'ü kullanır. Ağırlıklar: AI etkisi
  %35, temel analiz %28, analist %22, momentum %15.
  - Yeni momentum bileşeni: hissenin XU100'e göre 20 ve 60 işlem günlük göreli
    getirisi (±%25 göreli performans 0–100 bandına eşlenir).
  - TEFAS fon akımı skordan çıkarıldı: piyasa geneli tek bir sayı olduğu için
    her hisseye aynı puanı (47) veriyor ve yalnız analist verisi olan hisseleri
    "iki bileşenli" gösteriyordu.
  - Analist konsensüsü 180 günden eski tavsiyeleri saymaz, kalanları 90 günlük
    yarı ömürle ağırlıklandırır; ortalama tavsiye yaşı arttıkça güven düşer.
  - Güveni %60'ın altındaki skorlar nötre (50) doğru orantılı çekilir; ham
    skor `evidence.raw_score` alanında saklanır.
  - Geçmiş bir tarih için hesaplanan skor o tarihte bilinmeyen veriyi kullanmaz.
- Sinyal doğruluğu tablosu BIST100'e göre fazla getiriyi ve endeksi yenme
  oranını gösterir; mutlak getiri ikinci satıra taşındı.
- `run_once signals --days N` ile v3 skor geçmişi geriye dönük doldurulabilir.
- Paper portföy risk varsayılanları: zarar-kes %15, sektör limiti %30,
  yeniden dengeleme açık (kâr-al ve takip eden stop kapalı). `/sistem`
  ekranında kaydedilmiş değerler geçerliliğini korur.
- Paper portföy aynı gün en fazla 3 yeni pozisyon açar; tek bir haberin
  portföyün büyük bölümünü aynı gün doldurması engellenir. Strateji sürümü
  `paper-v2`.
- Paper portföy sayfasında BIST100'e göre fazla getiri kartı.
- Piyasa dışı haberler (spor, kültür-sanat, hava durumu, asayiş) kural
  tabanlı bir ön filtreyle Gemini'ye gönderilmeden `filtered` olarak
  işaretlenir. Ticker veya ekonomi terimi içeren her haber yine
  değerlendirilir. AI Analizleri listesi ve sayaçlar bu kayıtları göstermez.

### Yükseltme notu

Migration'lardan sonra v3 geçmişini bir kez doldurun:
`docker compose exec api python -m scripts.run_once signals --days 180`.
Doldurulmadan backtest ve doğruluk tablosu yalnız yeni günleri görür.

### Düzeltildi

- Şirket karşılaştırmasında konsensüs getiri potansiyeli 100 kat büyük
  gösteriliyordu (+6.454% yerine +64,5%).
- Dünya ve Foreks haberlerinde `&#039;` gibi çözülmemiş HTML kodları
  görünüyordu; toplayıcı düzeltildi, mevcut kayıtlar migration ile temizlenir.
- Veri kaynağı ve zamanlama etiketlerindeki eksik Türkçe karakterler.
- Karşılaştırma tablosunda fiyat ve skorlar Türkçe sayı biçimiyle gösterilir.
- `robots.txt` ve site simgesi eklendi (önceden 404).
- Temel analiz toplayıcısı gündemdeki hisseleri alfabetik sıralayıp ilk 50'yi
  aldığı için THYAO, PGSUS gibi alfabenin sonundaki hisseler hiç
  işlenmiyordu. Artık tüm evren günlük 120'lik partilerle dönüşümlü
  güncellenir (önce hiç çekilmemişler, 7 günde bir yenileme).
- Hisse evreninde payları borsada işlem görmeyen şirketler ve borçlanma aracı
  ihraççı kodları (ACP, ALK, TGB gibi) artık pasif; sinyal ve sayaçlara
  girmez.
- Bileşik Sinyaller sayfası soğuk önbellekte ~20 sn bekleyip doğruluk
  tablosu yerine hata gösteriyordu: doğruluk sorgusu yalnız sinyal dönemindeki
  fiyatları çeker, web istemcisi zaman aşımında yeniden denemez.
- Takvim sorgusu KAP gövde metni ve eklerini yüklemeden yalnız gereken
  kolonları okur.
- Kök layout `force-dynamic` olduğu için web tarafındaki `revalidate`
  ayarları etkisizdi; `apiGet` artık bu istekleri süreç içinde kısa süre
  önbelleğe alır (yalnız başarılı yanıtlar).

## [0.1.0] - 2026-10-08

İlk açık kaynak sürüm.

### Eklendi

- KAP bildirimleri, ekonomi haberleri (RSS), temel analiz, analist hedef
  fiyatları, kurum raporları, TEFAS fon akımları, BIST100 endeksi ve TCMB para
  politikası kararları için idempotent veri toplayıcıları.
- Gemini ile iki katmanlı (Tier 1 / Tier 2) haber ve KAP değerlendirmesi;
  varsayılan olarak kapalı, günlük token bütçesi ve maliyet korumalı.
- Hisse başına sürümlü 0–100 bileşik sinyal skoru, sinyal geçmişi ve isabet
  ölçümü.
- Komisyon, kayma ve risk kurallarıyla (stop-loss, take-profit, takip eden stop,
  pozisyon/sektör ağırlık sınırları) çalışan paper portföy motoru. Canlı emir
  iletimi yoktur.
- Sinyal stratejisi için backtest motoru ve BIST100 karşılaştırması.
- Next.js dashboard: piyasalar, sinyaller, haberler, KAP, AI analizleri,
  kurumsal görüş, makro, piyasa takvimi, karşılaştırma, izleme listesi,
  portföy, backtest ve sistem yönetimi ekranları; CSV dışa aktarma.
- `/sistem` ekranından tarama takvimi, çalışma zamanı ayarları, Gemini bağlantı
  testi, Telegram/webhook bildirimleri ve veri kalitesi izleme.
- Docker Compose / Coolify dağıtımı, sağlık kontrolleri, yedekleme/geri yükleme
  ve production ön kontrol betikleri.
- Yönetim ekranları için HTTP Basic Auth ve backend yazma uçları için yönetim
  anahtarı; `make init` ile güçlü parolaların otomatik üretilmesi.
