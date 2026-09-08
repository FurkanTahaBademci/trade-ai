# Codex Çalışma / Devir Notları

Son güncelleme: 2026-09-08 (Europe/Istanbul)

Bu dosya, Codex'in yaptığı değişiklikleri Claude ve diğer ajanların hızlıca
inceleyebilmesi için tutulur. Kanonik faz durumu `PROGRESS.md`, değişmemesi
gereken ürün kararları `CLAUDE.md` içindedir. Aşağıdaki 2026-09-07 (Claude)
girişi Codex değil, Claude tarafından yazıldı — paylaşılan tek devir
günlüğünü bölmemek için burada tutuluyor, başlıkta ajan belirtildi.

## 2026-09-08 — Arama ve izleme listesi sağlamlaştırması

- Komut paletinin yalnız masaüstünde görünen tetikleyicisi mobil üst çubuğa da
  taşındı. API isteği sonuçlandığında yazılmış sorguyu sıfırlayan effect döngüsü
  ayrıldı; boş sonuçta klavye indeksinin negatife düşmesi engellendi.
- Aramaya combobox/listbox erişilebilirlik ilişkileri, sayfa kaydırma kilidi ve
  görünür hata/yeniden deneme durumu eklendi. Market yanıtları tarayıcıya
  alınmadan önce doğrulanıp normalize ediliyor; arama sıralaması giriş dizisini
  artık mutasyona uğratmıyor.
- İzleme listesi aynı tarayıcının diğer sekmelerindeki `storage` olaylarını
  dinliyor. Tekrarlı, bozuk ve küçük harfli localStorage girdileri normalize
  ediliyor; servis hatası boş liste olarak gösterilmiyor ve artık aktif olmayan
  ticker kayıtları arayüzden temizlenebiliyor.
- Üç yeni saf fonksiyon testiyle web toplamı **28/28**; backend **150/150**,
  TypeScript, Next.js production build, diff kontrolü ve `npm audit` temiz.
  390 px headless Chrome görünümünde mobil arama düğmesi; CDP ile palet odağı ve
  API hata görünümü doğrulandı. Bu ortamda Docker soketi yetkisi olmadığı için
  yeni image/Compose provası ayrıca çalıştırılamadı.

## 2026-09-08 — Production preflight kontrolü

- `ops/preflight-production.sh` ve `make preflight` eklendi. Kontrol secret
  değerlerini yazdırmadan production modu, PostgreSQL parolası/URL'si, admin
  tokenı, HTTPS API adresi, CORS originleri, izinli hostlar ve Compose config'i
  doğruluyor; Gemini/N8N boşsa opsiyonel özellik uyarısı veriyor.
- Yerel geliştirme `.env` dosyası beklenen şekilde 6 production eksiğiyle kapıyı
  durdurdu. Güvenli sahte production değişkenleriyle pozitif senaryo tamamen geçti.
- Çalışan ortamda migration `c4e8a2b1d730 (head)`; PostgreSQL/Redis named volume,
  non-root/salt-okunur API-worker-web ve `unless-stopped` politikaları doğrulandı.

## 2026-09-08 — Liste ekranlarında sonsuz kaydırma

- `/haberler` ilk yüklemede 12 kayıt getiriyor; kullanıcı listenin sonuna
  yaklaşınca `IntersectionObserver` üzerinden sonraki 12 kayıt yükleniyor.
  Yükleme iskeleti, hata/yeniden deneme ve tüm kayıtlar görüldü durumları eklendi.
- Aynı yapı `/kap` (15'li), `/analizler` (12'li) ve `/sinyaller` (15'li)
  ekranlarına taşındı. `/piyasalar`, tam evren üzerinde çalışan aramayı korurken
  DOM'a 20'şer satır ekliyor. Eski sayfa numarası bileşeni tamamen kaldırıldı.
- Tarayıcı istekleri same-origin `/api/news-feed` route'u üzerinden internal API'ye
  ve diğer listeler `/api/list-feed/[kind]` üzerinden internal API'ye gidiyor;
  böylece API adresi tarayıcıdan erişilebilir olmasa da Coolify private ağ düzeni
  korunuyor. Kaynak/etiket filtreleri sonraki kademelerde de taşınıyor.
- Haber, KAP ve analiz cursor'ları tarih + benzersiz ID; sinyal cursor'ı skor +
  ticker + benzersiz ID kullanıyor. Eşit sıralama değerlerinde kayıt atlama ve
  mükerrer kart riski önlendi.
- Canlı Docker kontrolünde ilk ve ikinci 12'li sayfa arasında `overlap=0`.
  Headless Chrome 800px görünümde 12, uzun kaydırma görünümünde 120 kart render
  etti. KAP 15→90, Piyasalar 20→180 kayıt ilerledi; KAP ve Sinyal API'lerinde
  ardışık kademeler `overlap=0`. Production build, TypeScript, Ruff ve
  **106/106 test** temiz.

## 2026-09-07 — Faz 13 Docker/Coolify üretim hazırlığı tamamlandı

- Compose servislerine health/start/grace ayarları, bellek sınırları ve dönen
  JSON logları eklendi. PostgreSQL ile Redis dışarı port açmıyor; Redis AOF
  `everysec` kullanıyor. API/worker `tradeai`, web `node` kullanıcısıyla ve
  salt-okunur kök dosya sistemiyle çalışıyor; geçici yazımlar tmpfs üzerinde.
- Backend CORS origin ve izinli Host listesi environment üzerinden yönetiliyor.
  Web güvenlik başlıkları ile bağımsız `/health` route'u eklendi.
- `ops/backup-postgres.sh`, `restore-postgres.sh` ve `smoke-production.sh` ile
  `ops/COOLIFY.md` hazırlandı. Gerçek DB'den özel-format dump alındı; ayrı
  PostgreSQL 16 container'ına şema + migration/takvim verisi geri yüklenerek
  `c4e8a2b1d730` ve 12 takvim doğrulandı.
- Sıfır volume'lü ayrı Compose projesi kuruldu: PostgreSQL/Redis health, migration,
  12 takvim, API/web/worker açılışı başarılı oldu; test projesi ve volume'leri
  sonrasında kaldırıldı. Çalışan ortamda tüm production smoke rotaları HTTP 200.
- Next.js 15.0.3 → 16.3.4, React 18 → 19.2.8 ve PostCSS 8.5.28 güncellendi;
  `package-lock.json` + Docker `npm ci` kullanımına geçildi. Temiz production
  build ve `npm audit` 0 bulguyla geçti.
- Son kalite kapısı: tüm proje Ruff temiz, backend **102/102 test**, TypeScript
  kontrolü ve Compose config başarılı. Coolify'da kalan iş yalnız repo/domain/TLS
  ve production secret'larını bağlamak.

## 2026-09-07 — Faz 12 gelişmiş hisse grafikleri tamamlandı

- `PriceChart` etkileşimli client bileşenine dönüştürüldü. 1A/3A/6A/1Y/3Y/Tümü
  aralıkları, crosshair ve seçili gün tooltip'i, dönem getiri/düşük/yüksek
  kartları eklendi.
- Gerçek `price_daily` alanlarıyla min–maks fiyat bandı ve TL hacim barları;
  açılıp kapanabilen AOF, MA20, MA50 ve RSI(14) katmanları çiziliyor. Kaynakta
  `open` olmadığı için mum/OHLC verisi uydurulmadı.
- Hisse sayfası indeksli fiyat API'sinden mevcut tüm geçmişi bir kez alıyor;
  aralık değişimleri ek ağ isteği yapmadan tarayıcıda filtreleniyor. Üst başlıktaki
  90 günlük performans hesabı tüm-geçmiş yüklemesinden bağımsız tutuldu.
- Production Next.js build geçti. Canlı `/piyasalar/THYAO` 21 gerçek işlem günüyle
  HTTP 200; 1440px masaüstü ve 390px mobil headless Chrome görüntüleri görsel
  olarak doğrulandı. Uzun aralıklar üç yıllık collector backfill'i kadar veri gösterir.

## 2026-09-07 — Faz 11 dinamik tarama takvimi tamamlandı

- Statik collector cron'ları `c4e8a2b1d730` migration'ıyla PostgreSQL'deki
  `collector_schedule` tablosuna taşındı. 12 iş için varsayılan aralık, güvenli
  minimum, etkinlik, son enqueue ve sonraki çalışma zamanı kalıcı tutuluyor.
- Dakikalık `dispatch_due_schedules` tick'i vadesi gelen işleri deterministik
  job ID ile ARQ/Redis kuyruğuna ekliyor. 55 saniyelik Redis NX kilidi, birden
  fazla worker'ın aynı tick'i işlemesini; job ID ise aynı slotun yinelenmesini
  önlüyor. Kaçırılmış slotlar topluca çalıştırılmadan gelecekteki ilk slota taşınıyor.
- `GET/PATCH /api/schedules` ve `POST /api/schedules/{name}/run` eklendi.
  Production mutation'larında `ADMIN_API_TOKEN` zorunlu; Next.js server action
  anahtarı tarayıcıya açmadan interval, duraklat/etkinleştir ve manuel çalıştırma
  işlemlerini yapıyor. Değişiklikler `schedule_audit_log` içinde tutuluyor.
- `/sistem` artık haber ve KAP en üstte olmak üzere 12 takvimi, son/sonraki
  çalışma bilgisini ve güvenli minimum aralığı gösteriyor. Haber varsayılanı 5 dk.
- Canlı Docker testi: haber 5→10→pause→5; ayrıca 5→7 sonrası api/worker/web
  container recreate edildi, değer PostgreSQL'den 7 olarak geri geldi ve 5'e
  döndürüldü. Otomatik dispatcher vadesi gelen sinyal işini tek kez kuyruğa aldı;
  manuel çalıştırma da worker'da başarıyla bitti. Migration head `c4e8a2b1d730`,
  web build ve Ruff temiz, **99 test geçti**.

## 2026-09-07 — Yeni ürün kuyruğu

- Uygulama sırası kanonik plana Faz 11 tarama takvimi yönetimi, Faz 12 gelişmiş
  hisse grafikleri ve Faz 13 Docker/Coolify üretim hazırlığı olarak eklendi;
  mevcut backtest işi Faz 14'e taşındı.
- Haber collector'ı bugün statik ARQ cron ile her 5 dakikada bir, KAP işinden
  30 saniye sonra çalışıyor. Hedef; `/sistem` üzerinden takvimi görmek/değiştirmek,
  duraklatmak ve elle çalıştırmak. Ayarlar PostgreSQL'de kalıcı, tetikleme
  çoklu-worker durumunda Redis kilitli ve yönetim işlemleri audit kayıtlı olacak.
- Hisse detayında mevcut temel 90 günlük kapanış grafiği korunacak; tarih aralığı,
  hacim, min/max/AOF, tooltip ve göstergelerle geliştirilecek. Kaynak `open` alanı
  vermediği için uygun kaynak doğrulanmadan mum verisi uydurulmayacak.
- Yeni tablolar migration ile PostgreSQL'e eklenecek; API/web/worker stateless
  kalacak. Coolify öncesinde volume/yedek-geri yükleme, private network, health,
  restart kalıcılığı ve temiz deploy smoke testi zorunlu kabul edildi.

## 2026-09-07 — Birleşik hisse detayı, sakin tema ve TCMB faiz modülü

- Hisse detayı artık tek ticker altında fiyat grafiği, 12 finansal metrik,
  bileşik skor bileşenleri, analist konsensüsü ve kurum görüşleri, ilgili haber,
  KAP, AI değerlendirmeleri, paper pozisyon/işlem geçmişi ve son TCMB faiz
  ortamını birlikte gösteriyor. Fiyat/finansal/görüş/gündem/analiz anchor
  kısayolları uzun sayfada gezinmeyi kolaylaştırıyor.
- Paper pozisyon ve işlem endpoint'lerine opsiyonel tam ticker filtresi eklendi;
  hisse sayfası portföyün tamamını taşımıyor.
- Tema tokenlarındaki neon sarı `#c7ff4a`, düşük parlaklıklı mavi `#7fa6e8`
  ile değiştirildi. Arka plan radyal ışığı ve kontrast tokenı aynı palete uyarlandı.
- Resmî TCMB PPK yıl sayfası collector'ı geçmiş karar URL'lerini ve yaklaşan
  toplantıları topluyor. Karar metni politika/koridor oranlarını, baz puan
  değişimini, özeti ve yönlendirmeyi ayrıştırıyor. Migration head
  `b7d4e9a2c610`; API, 06:30 cron ve manuel CLI bağlandı.
- Etki alanı tahmin edilen fiyat getirisi değildir: HIKE/CUT/HOLD kararına göre
  hisse, banka, gayrimenkul, TL ve tahvil aktarım kanallarını açıklayan sürümlü
  `rule_based_scenario_v1` sözlüğüdür ve ekranda disclaimer taşır.
- Canlı koşu 2025-2026 için 17 tarih buldu: 14 karar + 10 Eylül/22 Ekim/
  10 Aralık 2026 toplantıları. Tekrar koşusu `new=0`, `details_fetched=0`.
  Canlı test, 20 Mart 2025'te politika faizi sabitken koridor artışının ilk
  sınıflandırmayı yanıltabildiğini yakaladı; politika oranı özel parser'ıyla
  düzeltildi ve `--refresh` ile mevcut kayıtlar yenilendi.
- Ruff/offline DDL/Next.js production build temiz; **91 test geçti**. `/makro`
  ve `/piyasalar/THYAO` Docker üzerinden HTTP 200 ve headless Chrome ekran
  görüntüsüyle görsel olarak doğrulandı.

## 2026-09-07 — Faz 10 sağlık ve alarm çekirdeği (ara teslim)

- Redis'teki collector başarı/hata kayıtları ilk kez `/health/detailed` içine
  bağlandı. KAP/haber için 20 dakika; günlük/iş günü kaynakları için hafta sonu
  toleranslı 72-96 saatlik tazelik eşikleri var.
- Worker heartbeat'i artık Redis'e yazılıyor. Ortak rapor `healthy`, `stale`,
  `error` ve `pending` durumlarını; sorun ve bekleyen bileşen sayılarını döndürüyor.
- Collector hataları anında, periyodik `monitor_system` işi gecikmiş kaynakları
  beş dakikada bir değerlendiriyor. N8N alarmı yapılandırılmış JSON gönderiyor;
  Redis fingerprint/cooldown aynı sorunu varsayılan 3600 saniye içinde tekrar
  göndermiyor. Webhook boşsa dış istek yapılmıyor.
- Yeni `/sistem` ekranı altyapı, worker ve sekiz veri hattını gösteriyor; ana
  sayfadaki genel sağlık göstergesi artık yalnız HTTP erişimini değil raporun
  gerçek `status` alanını kullanıyor.
- Ruff temiz, Next.js production build başarılı, test suite **85 passed**.
  N8N URL'si olmadığı için gerçek dış webhook çağrısı yapılmadı; sahte istemciyle
  payload ve dedup davranışı doğrulandı.

## 2026-09-07 — Faz 8 paper portföy motoru ve portföy ekranı

- Canlı emir göndermeyen, long-only ve kaldıraçsız `paper-v1` motoru eklendi.
  Varsayılan portföy 1.000.000 TL; giriş skoru `>=75`, güven `>=0,25`, kapsam
  `>=2`; çıkış skoru `<40`; en fazla 10 pozisyon ve pozisyon başına `%10` risk.
  İşlemlerde `%0,10` komisyon, `%0,05` kayma ve 1.000 TL minimum büyüklük var.
- `paper_portfolio`, `paper_position`, `paper_trade` ve günlük
  `paper_portfolio_snapshot` tabloları `f95c4a21d8e7` migration'ıyla eklendi.
  Deterministik execution key aynı gün/yön/strateji emrini mükerrer yazdırmıyor.
- Portföy liste/detay, pozisyon, işlem ve performans API'leri; manuel `paper`
  CLI komutu ve sinyal işinden sonra 18:46 ARQ cron'u bağlandı.
- Next.js `/portfoy` sayfası toplam değer/nakit/K-Z/komisyon kartlarını,
  performans SVG grafiğini, açık pozisyonları ve işlem geçmişini gösteriyor.
  Sidebar'a eklendi ve mevcut merkezi CSS tema değişkenlerini kullanıyor.
- Doğrulama: Ruff temiz, offline migration DDL başarılı, web production build
  başarılı ve **78 test geçti**. Docker migration head `f95c4a21d8e7`; canlı
  API uç noktalarının tamamı ve `/portfoy` HTTP 200 döndü.
- Test DB'sinde ilk uygun 10 adayın 30 günlük fiyatı (200 satır) tamamlandı.
  Paper koşusu ilk seferde 10 alış açtı; hemen tekrarı `trades=0` döndürdü.
  DB'de 10 işlem/10 benzersiz execution key ve 10 pozisyon var. İlk toplam
  değer 998.502,40 TL (`-%0,1498`); bu, alış komisyonu ve kayma varsayımına uygun.

### Sıradaki iş

Faz 10 — alarm ve gözlemlenebilirlik. Faz 4'ün gerçek Gemini API anahtarı
doğrulaması kullanıcı anahtarı sağlanana kadar ayrı açık madde olarak kalıyor.

## 2026-09-07 (Claude) — Faz 6 kapanışı: kurum PDF hattı (PhillipCapital)

### Neden bu kaynak

Faz 6'nın açık maddesi kurum PDF hattıydı. Bu oturumda ~15 arac kurumun
araştırma sayfası araştırıldı (İş Yatırım `arastirma.isyatirim.com.tr`, Ak
Yatırım, Oyak Yatırım, QNB Finansinvest, Tacirler, Şeker, Deniz, Halk,
Phillip Capital, Tera, ...). Çoğu ya üyelik duvarının arkasında ("Üye ve
Müşterilere Özel İçerik") ya da JS ile render edilen SPA. **PhillipCapital
Türkiye'nin `phillipcapital.com.tr/arastirma-urunleri` sayfası** login
gerektirmeyen, sunucu tarafında render edilen, kategori/sayfa query
parametreleriyle filtrelenebilen tek kaynak olarak doğrulandı. "Şirket
Raporları" kategorisinde 138 gerçek rapor bulundu (2023-2026 arası).

### Tamamlananlar

- `app/collectors/institutional_reports.py` (yeni dosya): liste sayfasını
  keşfeder (`_ProductListParser`, azalan tarih sıralı sayfalama + erken
  durma), yeni PDF'leri indirir, `pdftotext -layout` (poppler-utils,
  subprocess) ile sayfa 1'i metne çevirir, "Bloomberg Ticker" satırından
  sonraki ~900 karakterlik pencerede etiket bazlı (TR/EN çoklu varyant)
  hedef fiyat/referans fiyat/getiri potansiyeli/öneri alanlarını ayrıştırır.
- Yeni tablo YOK — mevcut `AnalystRecommendation`/`AnalystConsensus` şeması
  yeniden kullanıldı (`source="phillipcapital_pdf"`, `source_key`=PDF GUID).
  `raw_data` JSONB'de checksum (`pdf_sha256`), boyut, başlık, kategori.
- `analysts.py`: konsensüs yeniden hesaplama mantığı `recompute_analyst_consensus()`
  ortak fonksiyonuna çıkarıldı (hem `AnalystCollector` hem yeni collector
  kullanıyor — DRY, "collectors/base.py tek doğru yazılır" ruhunu paylaşılan
  yardımcı fonksiyonlara da genişletti). `normalize_recommendation()`
  sözlüğüne İngilizce (Outperform/Market Perform/Underperform/Neutral/
  Overweight/Underweight) ve PhillipCapital'a özgü "Endeks Üzeri Getiri"
  (İş Yatırım'ın "Endeks Üstü Getiri" ifadesinden farklı, aynı anlamda BUY
  sözcüğü — gerçek ASTOR fixture'ında yakalandı) eklendi.
- ARQ cron `collect_institutional_reports` (07:45, analist işinden sonra);
  manuel `python -m scripts.run_once institutional-reports [--max-pages N]`.
- Dockerfile'a `poppler-utils` eklendi (`pdftotext` için).
- Fixture'lar (`backend/tests/fixtures/institutional_reports/`): liste
  HTML'i (4 gerçek kart + sayfalama) ve 4 gerçek PDF'in `pdftotext -layout`
  çıktısı (EREGL TR/EN, ASTOR TR başlangıç raporu, KMPUR "Toplantı Notu"
  atlanma senaryosu) — ham PDF binary'leri commit edilmedi (KAP ekinde
  olduğu gibi, 300-1000 KB aralığında, gereksiz repo şişmesi).
- 9 yeni test `tests/test_institutional_mapping.py`'e eklendi (aynı Faz 6
  test dosyası — ayrı dosya açılmadı).

### Canlı doğrulamada bulunan ve düzeltilen hata

İlk canlı koşuda **collector idempotency hatası** yakalandı: "Bloomberg
Ticker" taşımayan şablonlar (`skipped_unparseable_template`) hiçbir zaman
DB'ye yazılmadığı için ikinci koşuda da "new" sayılıp yeniden indirilip
ayrıştırılıyorlardı — hem gereksiz ağ trafiği hem de sayfalama erken durma
optimizasyonunu bozuyordu (bir sayfada en az bir atlanan rapor olduğu sürece
collector sonsuza kadar tüm sayfaları tarardı). Redis SET
(`institutional_reports:skipped_guids`) ile düzeltildi — atlanan GUID'ler de
`existing_keys`'e dahil ediliyor artık. Bu, DB satır idempotency'sinin
("iki kez çalıştır, ikinci sıfır satır" — vibe kural #5) ağ/iş idempotency'si
ile aynı şey olmadığını gösteren somut bir örnek: DB'de zaten hep 0 yeni
satır vardı (`accepted=0`), ama collector gereksiz yere PDF indirmeye devam
ediyordu.

### Canlı doğrulama (Docker + gerçek PostgreSQL/Redis)

- Docker `poppler-utils` ile yeniden build edildi; worker 19 fonksiyonla
  (yeni cron dahil) başladı.
- 2 sayfa sınırlı ilk koşu: 20 keşif, 3 kabul (formal şablon), 17 atlama.
  İkinci koşu (düzeltme öncesi kod) `new=17` döndürerek hatayı ortaya
  çıkardı. Düzeltme sonrası üçüncü koşu yalnız sayfa 1'i kontrol edip
  `new=0`, sıfır PDF indirme.
- Redis atlama önbelleği temizlenip tam geri dolum çalıştırıldı: 138 rapor
  keşfedildi (14 sayfa), 21 kabul, 114 şablon uyumsuzluğu, 0 indirme hatası.
  Tekrar koşu `new=0`. DB'de 24/24 `source_key` benzersiz (bazı raporların
  ayrı TR/EN PDF'i var — ikisi de meşru ayrı kayıt, `calculate_consensus`
  zaten (ticker, institution) bazında dedup ediyor).
- Docker içinde **65/65 test geçti** (58 → 65); Ruff/format değiştirilen
  dosyalarda temiz; `alembic check` yeni işlem bulmadı (head hâlâ
  `c62f1a8e4d73` — şema değişmedi).
- API doğrulaması: `GET /api/analysts/GRSEL/consensus` → `institution_count:
  1`, `source_breakdown: {"phillipcapital_pdf": 1}`, `recommendation_score:
  100` (BUY), `average_target: 564.0`.

### İncelemede özellikle bakılacak kararlar

1. Raporların yalnızca ~%15'i ("Bloomberg Ticker" satırı taşıyan göreceli
   yeni şablon) güvenilir ayrıştırılıyor. Eski kapak/"Toplantı Notu"
   şablonları isme dayalı tahmin yapılmadan sessizce atlanıyor — proje
   kuralı ("eşleme mantığı asla isme dayanmamalı") burada bilinçli olarak
   kapsam daraltmayı, yanlış eşlemeye tercih ediyor.
2. Redis atlama önbelleği kalıcı değildir (Redis verisi kaybolursa 114
   şablon-uyumsuz rapor bir kereliğine yeniden indirilir) — bu kabul
   edilebilir, çünkü DB idempotency'si (unique `source_key`) her koşulda
   korunuyor; önbellek sadece bant genişliği optimizasyonu.
3. `recompute_analyst_consensus()` ortak fonksiyonu artık üç yerden
   tetikleniyor (AnalystCollector, InstitutionalReportCollector, ve
   dolaylı olarak günlük 07:30/07:45 cron'ları) — konsensüs hangi
   collector'ın son çalıştığına bakmaksızın tüm `analyst_recommendation`
   tablosunu okuyup yeniden hesaplıyor, bu yüzden sıralama/zamanlama
   hassasiyeti yok.

### Sıradaki iş (bu kaydın yazıldığı andaki durum)

Faz 7 ve o tarihteki özellikleri kapsayan Faz 9 dashboard tamamlandı. Faz 8
sonraki Codex kaydında tamamlandı; güncel sıradaki iş Faz 10'dur. Faz 4'ün
gerçek Gemini API anahtarı doğrulaması hâlâ ayrı açık madde (kullanıcı tarafında).

## 2026-09-07 — Faz 7 bileşik skor + sinyal motoru ve dashboard entegrasyonu

- `composite_signal_snapshot`: ticker/gün/model sürümü doğal anahtarı; skor,
  pozitif/nötr/negatif teknik etiket, güven, kapsam ve kaynak kanıtları.
- V1 sabit ağırlıkları LLM `%35`, temel `%30`, analist `%25`, TEFAS piyasa
  akımı `%10`. Eksik bileşenler sıfır değildir; mevcut ağırlıklar normalize
  edilir ve en az iki kaynak zorunludur.
- LLM dokümanları Tier 2 önceliği, confidence ve recency decay ile; analist
  bileşeni oy dağılımı + hedef potansiyeliyle; piyasa rejimi akım büyüklüğü +
  pozitif fon genişliğiyle hesaplanır. Model sürümü `v1`.
- API liste/filtre/geçmiş, manuel CLI ve LLM sonrasında 10 dakikalık ARQ cron
  eklendi. Arayüzde ayrı `/sinyaller` sıralaması, ana sayfa ilk beş ve hisse
  detayında bileşen barları bulunuyor.
- Docker/PostgreSQL canlı koşu x2+: 91 aday, 88 snapshot, 3 düşük kapsam;
  tekrar `new=0`, `updated=88`. Alembic head `e84b2b3d91f0`, 72 test geçti.

## 2026-09-07 — Faz 6 analist konsensüsü ve TEFAS fon akımı (çekirdek)

### Tamamlananlar

- Analist görüş geçmişi ile günlük ticker konsensüsü için iki tablo; TEFAS fon
  snapshot'ı ile günlük fon akım agregası için iki tablo eklendi. Migration
  head `c62f1a8e4d73`.
- İş Yatırım'ın resmi takip tablosu doğrudan kurumsal kaynak, Halka Arz Takvimi
  çok-kurumlu agregatör olarak ayrık parser'larla bağlandı. Kurum bazında yalnız
  son görüş konsensüse giriyor; tarih eşitliğinde doğrudan kaynak agregatörü
  eziyor. Tavsiyeler BUY/HOLD/SELL/REVIEW sözlüğüne normalize ediliyor.
- Konsensüs kurum ve oy sayıları, ortalama/medyan/min/max hedef, son EOD fiyata
  göre potansiyel, hedef dağılımı ve 0-100 görüş skorunu saklıyor.
- TEFAS `fonGnlBlgSiraliGetir` ve `dagilimSiraliGetirT` yanıtları fon/tarih
  anahtarında birleştirildi. Net giriş/çıkış tahmini
  `AUM_t - AUM_(t-1) * fiyat_t / fiyat_(t-1)`; yurtiçi hisse akımı bunun güncel
  `hs` ağırlığıyla çarpımıdır. Bu bir tahmindir, TEFAS'ın yayımladığı doğrudan
  nakit akışı alanı değildir.
- Analist/fon API'leri, günlük 07:30 ve 20:00 cron'ları, manuel CLI komutları ve
  gerçek-kaynak fixture testleri eklendi.

### Canlı doğrulama

- Analist x2: iki kaynak da 200; 53 İş Yatırım + 374 agregatör = 427 kayıt,
  90 ticker konsensüsü. İkinci koşu `new=0`; DB 427/427 doğal anahtar benzersiz.
  THYAO için 9 kurum, 400-580 TL hedef bandı ve kaynak kırılımı API'de döndü.
- TEFAS YAT x2: 7 günlük istekte 10.202 snapshot, 10.037 dağılım eşleşmesi ve 5
  işlem günü agregası. İkinci koşu `new=0`; DB 10.202/10.202 doğal anahtar
  benzersiz. AAV snapshot ve günlük piyasa agregası API'den doğrulandı.
- Docker suite **58 passed**; Alembic head/check, Ruff/format ve whitespace
  kontrolleri temiz. Worker 17 fonksiyonla yeni iki cron'u kaydetti.

### Açık kalan Faz 6 işi

Kilit ürün kararındaki özgün kurum PDF hattı henüz eklenmedi. Mevcut doğrudan
İş Yatırım HTML kaynağı güvenilir kurumsal kapsam sağlıyor, ancak PDF rapor
keşfi/indirme/checksum/metin-tablosu çıkarımı tamamlanmadan Faz 6 ✅ yapılmadı.

**Güncelleme (2026-09-07, Claude):** Kurum PDF hattı eklendi ve Faz 6 ✅
yapıldı — bkz. dosyanın başındaki "Faz 6 kapanışı: kurum PDF hattı
(PhillipCapital)" girişi.

## 2026-09-07 — Faz 5 temel analiz motoru

### Tamamlananlar

- İş Yatırım'ın `MaliTablo` yanıtındaki kaynak kalemleri kayıpsız saklayan
  `financial_fact`, bunlardan deterministik türetilen oran ve skorları tutan
  `fundamental_snapshot` tabloları eklendi. Migration head `a91e5c7d3f42`.
- Kaynak finansal grup şirketten şirkete değişebildiği için collector
  `XI_29`, `UFRS`, `UFRS_K` sırasıyla keşif yapıyor. İstenen yılların
  3/6/9/12 dönemlerini aynı grup üzerinden çekiyor ve doğal anahtarla upsert
  ediyor.
- Eşlenen çekirdek `itemCode` alanları: dönen varlık/nakit, kısa ve uzun
  finansal borç, kısa vadeli yükümlülük, özsermaye, satış, brüt/faaliyet/net
  kâr, amortisman, faaliyet ve serbest nakit akışı.
- Büyüme, kârlılık, bilanço ve nakit akışı bileşenlerinden 0-100 teknik skor
  üretiliyor. Skor yatırım tavsiyesi değil, Faz 7 bileşik sinyaline girdi olacak
  deterministik bir sıralama sezgisi. Yeterli oran/bileşen yoksa `NULL` kalıyor.
- Explicit ticker/yıl aralıklı CLI, son 30 günün ilgili LLM sonuçlarından en
  fazla 50 aktif ticker seçen günlük 07:00 ARQ işi ve snapshot/ham veri API
  route'ları bağlandı.

### Doğrulama

- Kaynak uç nokta canlı THYAO verisiyle doğrulandı; gerçek yanıtın 14 çekirdek
  satırlık küçültülmüş örneği fixture olarak kaydedildi.
- THYAO 2025-2026 collector koşusu ilk çalışmada 880 yeni finansal gerçek ve 6
  snapshot oluşturdu. Aynı komut ikinci kez `new=0` döndürdü; DB sayımı
  880 toplam / 880 benzersiz doğal anahtar / 6 snapshot.
- Çalışan API'de en güncel snapshot oranları ve `2025/12/3C` satış kalemi
  doğrulandı. API/worker imajları sağlıklı; worker 13 fonksiyonla ve yeni cron
  kaydıyla başladı.
- Gerçek PostgreSQL'de Alembic head `a91e5c7d3f42`; `alembic check` temiz.
  Docker suite **52 passed**; Ruff ve diff whitespace kontrolleri temiz.

### Sıradaki iş

Faz 6 — analist tavsiyeleri, TEFAS fon akımları ve konsensüs. Faz 4'ün gerçek
Gemini çağrısı API anahtarı sağlanana kadar ayrı açık madde olarak kalıyor.

## 2026-09-07 — Faz 4 LLM değerlendirme katmanı

### Tamamlananlar

- Haber ve KAP için ortak `llm_evaluation` şeması eklendi. Değerlendirme
  anahtarı kaynak türü/id, içerik hash'i, prompt sürümü, model, tier ve varsa
  parent Tier 1 anahtarından deterministik üretiliyor.
- Başarılı/başarısız/running durumları, en fazla üç deneme, 30 dakikalık stale
  recovery, input/output/total token, latency ve ham/yapılandırılmış çıktı
  denetlenebilir biçimde saklanıyor.
- Tier 1 tüm backlog'u `gemini-3.7-flash` ile süzer; Tier 2 yalnız ilgili,
  varsayılan 70+ etkili, derin analiz işaretli ve aktif BIST ticker'lı kayıtlara
  `gemini-3.1-pro-preview` ile uygulanır. Tier 1 düşük, Tier 2 orta thinking.
- Backlog seçimi yalnız son N kayda bağlı değil: hiç işlenmemiş kaynaklar ile
  retry edilebilir hata/stale kayıtlar ayrıca SQL'den seçiliyor.
- Promptlar `app/llm/prompts/v1.md` içinde sürümlü. Structured output şeması
  promptta tekrarlanmıyor; Pydantic JSON Schema SDK config'ine veriliyor.
  Kaynak delimiter karakterleri kaçışlanıyor ve prompt injection talimatları
  açıkça güvenilmeyen veri kabul ediliyor.
- Harcama güvenliği için `LLM_ENABLED=false`, günlük token limitleri, batch ve
  kaynak karakter limitleri eklendi. Anahtar olsa bile açıkça enable edilmeden
  API çağrısı yapılmıyor.
- `google-genai>=1.60`, değerlendirme API route'ları, 10 dakikalık ARQ işi ve
  `scripts.run_once llm` CLI komutu bağlandı.

### Doğrulama

- Docker build `google-genai 2.22.0` ile başarılı. Kullanılan
  `response_json_schema`, `ThinkingConfig(thinking_level=...)` ve paketlenmiş
  prompt dosyası çalışan imaj içinde doğrulandı.
- Alembic gerçek PostgreSQL head `f47a1c8d6b20`; `alembic check` yeni işlem
  bulmadı. JSONB/GİN indeksleri, skor CHECK constraint'leri ve parent anahtarı
  gerçek tabloda oluştu.
- Sahte Gemini geçidiyle gerçek DB koşusu: Tier 1 ve Tier 2 birer başarılı,
  parent bağlantısı doğru, 200 input/100 output token toplamı, hayalî ticker
  elendi. Aynı iki değerlendirme tekrar çağrıldığında ikisi de `skipped`.
  Geçici test satırları koşu sonunda silindi.
- `LLM_ENABLED=false` ile gerçek CLI ve otomatik cron ücretli çağrı yapmadan
  `{enabled: false}` döndü.
- Docker suite: **45 passed**. Ruff, OpenAPI, `/api/evaluations` boş liste ve
  bulunamayan detay 404 davranışı temiz.

### Açık kalan tek doğrulama

Ortamda `GEMINI_API_KEY` yok. Gerçek ücretli API çağrısı yapılmadı ve bu yüzden
Faz 4 kanonik durumda 🔶. Anahtar sağlandığında önce `LLM_BATCH_SIZE=1` ile CLI
çalıştırılmalı; structured yanıt ve gerçek usage metadata görüldükten sonra
normal batch'e çıkılmalı.

### Bu devir notunun devamı

Faz 5 uygulanıp doğrulandı; güncel sonuç dosyanın başındaki Faz 5 bölümündedir.
Faz 4 canlı API doğrulaması anahtar gelince ayrıca tamamlanabilir.

## 2026-09-07 — Faz 3 haber toplayıcı

### Tamamlananlar

- `news_article` şeması ve `d3f6a81c2e90` migration'ı eklendi. Kimlik,
  canonical URL'nin SHA-256 özeti; URL ayrıca okunabilir biçimde korunuyor.
- Bloomberg HT ve Investing.com.tr RSS akışları `NewsCollector` altında
  toplandı. Tek kaynak hatası diğer kaynağı durdurmuyor; kaynak/satır hataları
  sonuç özetinde görünür kalıyor.
- Takip query parametrelerini ve fragment'i atan deterministik URL
  canonicalization eklendi. İkinci koşu aynı URL hash'lerini upsert ediyor.
- Tüm yayın zamanları UTC'ye çevriliyor. Investing RSS tarihinin timezone
  yazmayan değeri, aynı haberin resmi sayfasındaki TRT gösteriminden üç saat
  geride olduğu görülerek UTC kabul edildi.
- Ticker eşlemesi aktif instrument kodlarıyla sınırlı. Metinde açık büyük harfli
  kod veya URL token'ı yoksa şirket adına bakılarak çıkarım yapılmıyor.
- `/api/news` liste/kaynak/ticker/cursor filtreleri ve `/api/news/{id}` detayı,
  ARQ 5 dakikalık cron'u ve `scripts.run_once news` CLI komutu bağlandı.

### Doğrulama

- Değiştirilen Python dosyalarında Ruff temiz; Alembic offline PostgreSQL DDL
  üretimi başarılı.
- Docker API/worker imajları yeniden oluşturuldu, API açılışında migration
  uygulandı; gerçek PostgreSQL head `d3f6a81c2e90`.
- Canlı RSS x2: ilk koşu `listed=30, new=30`, ikinci koşu `listed=30, new=0`;
  her ikisinde iki kaynak başarılı ve satır hatası yok. DB 30 satır/30 benzersiz
  hash: Bloomberg HT 20, Investing 10.
- Docker test konteynerinde fixture klasörü salt okunur mount edilerek
  `pytest -q` çalıştırıldı: **34 passed**.
- API'de iki öğelik liste, `source=investing_tr` filtresi ve bulunamayan detay
  için 404 yanıtı gerçek çalışan container üzerinden doğrulandı.

### İncelemede özellikle bakılacak kararlar

1. Investing'in offset'siz saati UTC kabul ediliyor; kaynak formatı değişirse
   fixture ve resmi sayfa karşılaştırmasıyla yeniden doğrulanmalı.
2. Ticker eşlemesi bilinçli olarak muhafazakâr. Düşük false-positive uğruna
   şirket adı geçen fakat kodu yazmayan haberler şimdilik eşleşmeyebilir.
3. Tüm ham RSS satırı `raw_entry` içinde korunuyor; şema değişimlerini geriye
   dönük incelemek mümkün.

### Bu devir notunun devamı

Buradaki Faz 4 planı uygulandı; güncel sonuç ve açık canlı API doğrulaması
dosyanın başındaki Faz 4 bölümündedir.

## 2026-09-06 — Faz 2 KAP toplayıcı

### Tamamlananlar

- `kap_disclosure` ve `kap_attachment` şemaları + Alembic migration eklendi.
- Liste sorgusu geniş tarih aralığı yerine gün gün çalışıyor. KAP tek günlük
  sorgusu resmi uç noktada 2026-09-04 için 291 kayıt dönerek doğrulandı.
- Liste `disclosure_index`, ekler `objId` üzerinden upsert ediliyor.
- Yalnızca yeni veya daha önce detayı alınamamış bildirimlere detay isteği
  gidiyor. Eksik/başarısız ekler sonraki koşuda yeniden deneniyor.
- KAP HTML gövdesinden görünür Türkçe metin çıkarılıyor; ham HTML ve ham JSON
  kaybolmadan ayrıca saklanıyor.
- Ek şeması resmi detay yanıtından doğrulandı:
  `objId`, `fileName`, `fileExtension`.
- Gerçek KAP eki üzerinde Java serialization çözümü doğrulandı:
  bildirim `1659248`, objId `4028328d9f52dddd01a06d943dc11178`,
  sarmalayıcı 2.699.462 bayt, çıkan `%PDF-1.4` dosya 2.699.435 bayt.
- API, ARQ cron ve `scripts.run_once kap` CLI bağlantıları yapıldı.

### Doğrulama

- `backend/.venv/bin/pytest -q` → **26 passed**.
- Değiştirilen Python dosyalarında `ruff check` → temiz.
- `alembic upgrade head --sql` → üç migration için geçerli PostgreSQL DDL;
  `ticker_codes JSONB` + GIN index ve ek içeriği `BYTEA` olarak üretildi.
- FastAPI OpenAPI içinde üç KAP route'u doğrulandı.
- Gerçek binary örneği fixture/repo içine alınmadı (2,7 MB); parser testi aynı
  byte dizisi biçimini küçük deterministik payload ile kapsıyor.

### İncelemede özellikle bakılacak kararlar

1. Ek dosyaları ilk sürümde PostgreSQL `BYTEA` içinde tutma kararı. Basit ve
   yedeklenebilir; veri büyümesi görülünce S3 uyumlu depolama/retention gerekir.
2. `ticker_codes` isim eşlemesi yerine KAP kodlarını aynen JSONB listesinde
   tutuyor. Sorgu için GIN indeks var; Faz 7 sinyal eşlemesi koda dayanmalı.
3. Günlük KAP sonucu tam 2000'e ulaşırsa collector veri kaybı riskini gizlemek
   yerine hata veriyor. Böyle bir olayda üye/kategori bazlı bölme eklenmeli.
4. Tek ek indirme hatası tüm batch'i durdurmuyor; metadata ve hata saklanıp
   sonraki 5 dakikalık koşuda yeniden deneniyor.

### Docker doğrulaması (2026-09-06) — tamamlandı

- Sistem Docker Engine 29.1.3 (`overlayfs`) ve Compose v2 kuruldu. Ajanın eski
  oturumu yeni grup üyeliğini devralmadığı için komutlar `sg docker -c ...`
  ile çalıştırıldı; yeni kullanıcı oturumunda normal `docker` yeterli olmalı.
- `docker compose up -d --build` gerçek base image'larla başarılı. PostgreSQL
  ve Redis healthy; API `/health/detailed` sonucu `db/redis/status=ok`; ARQ
  worker ve Next.js dashboard çalışıyor.
- Hostta başka proje (`/home/furkan/Mizan`) 8000 portunu kullandığından ona
  dokunulmadı. Compose portları `API_PORT/WEB_PORT` ile ayarlanabilir yapıldı;
  git'e girmeyen yerel `.env` bu testte API için `18000` kullanıyor.
- Docker testiyle bulunan ve düzeltilen sorunlar:
  1. Runner'ın var olmayan `web/public` dizinini kopyalaması.
  2. `web/node_modules` yüzünden 404,72 MB build context; `web/.dockerignore`
     sonrası context 2,1 KB.
  3. Dashboard container'ının API için `localhost` kullanması;
     `API_INTERNAL_URL=http://api:8000` eklendi ve dashboard artık sağlık
     sonucunu doğru gösteriyor.
  4. KAP'ın `KRDMA, KRDMB, KRDMD` gibi çoklu kod alanını tek ticker sanan
     instrument collector. Kodlar ayrı satırlara açıldı, `kap_member_oid`
     unique kısıtı normal indekse çevrildi (`a7e2c4f98b11`).
- Gerçek PostgreSQL sonuçları:
  - Alembic head: `a7e2c4f98b11`.
  - Instrument x2: 757 KAP üyesi -> 807 ticker; DB 807 benzersiz ticker.
  - Prices x2 (`THYAO,ASELS,GARAN`, 30 gün): her seferinde 63 upsert; DB'de
    63 benzersiz `(ticker,date)`.
  - KAP ilk koşu: 293 yeni, 293 detay, 100 ek indirildi, 24 ek geçici hata.
  - KAP ikinci koşu: `new=0`, `details_fetched=0`; eksiklerden 6'sı indirildi.
  - 15:25 ARQ cron'u otomatik tetiklendi: `new=0`, `details_fetched=0`, kalan
    18 ek indirildi, `attachment_failures=0`.
    Son durum 293 benzersiz bildirim, 124 benzersiz ek metadata ve 124 içerik;
    eksik/kopya satır yok.
  - API eki `1659248/4028328d9f52dddd01a06d943dc11178` GET ile
    `255044462d312e34` (`%PDF-1.4`) olarak doğrulandı.
- Test suite çoklu ticker regresyon testiyle birlikte **26 passed**; ilgili
  değişikliklerde Ruff temiz ve Docker build yeniden başarılı.
- Takip işi: `npm install`, Next.js 15.0.3 için güvenlik uyarısı ve bağımlılık
  ağacında 2 high + 1 critical bulgu raporladı. Production öncesi kontrollü
  Next.js/dependency yükseltmesi yapılmalı; bu Docker doğrulama turunda sürüm
  değişikliği yapılmadı.

### Bu devir notunun devamı

Buradaki Faz 3 planı uygulanıp doğrulandı; güncel sonuç ve sıradaki iş dosyanın
başındaki 2026-09-07 bölümündedir.
