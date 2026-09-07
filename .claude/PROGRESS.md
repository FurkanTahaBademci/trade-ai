# Faz İlerleme Takibi

Durumlar: ⬜ başlanmadı · 🔶 devam ediyor · ✅ tamamlandı ve doğrulandı

## Faz 0 — İskelet + Coolify + Kaynak Doğrulama
🔶 Devam ediyor (kod tarafı bitti, Coolify'a bağlama kullanıcıda kaldı)

- [x] `.gitignore`, `.env.example`
- [x] `backend/` iskeleti: `pyproject.toml`, `Dockerfile`, `app/core/{config,db,redis,logging}.py`
- [x] `app/main.py` + `/health`, `/health/detailed`
- [x] Alembic kurulumu (`alembic.ini`, `alembic/env.py`, `script.py.mako`)
- [x] `app/tasks/schedule.py` — ARQ worker iskeleti (heartbeat cron)
- [x] `backend/scripts/smoke_sources.py` — KAP liste/detay, TEFAS, RSS (bloomberght,
      investing_tr), `isyatirimhisse` kontrolü
- [x] **smoke_sources.py çalıştırıldı — 6/6 kaynak OK** ✅ (bkz. aşağıdaki
      "Doğrulanmış kaynak bulguları")
- [x] `docker-compose.yml` (postgres, redis, api, worker, web)
- [x] `web/` (Next.js 15 App Router) iskeleti + `/health/detailed` çağıran ana sayfa
- [x] `ops/Caddyfile` (yerel geliştirme için, Coolify prod'da kendi proxy'sini kullanır)
- [x] `Makefile`, `README.md`
- [x] `backend/tests/fixtures/` — KAP liste/detay, TEFAS dağılım, 2 RSS feed'in
      gerçek yanıtları kaydedildi (Faz 2+ ağsız regresyon testleri için)
- [x] `docker compose config --quiet` — Compose 5.5.0 ile değişken çözümleme ve
      servis grafiği doğrulandı.
- [x] Docker denemesinde `web/public` yokken runner'ın dizini kopyalaması
      hatası bulundu; builder stage dizini deterministik oluşturacak şekilde
      düzeltildi.
- [x] Web production build'i hem host Node hem gerçek Docker multi-stage build
      içinde başarıyla tamamlandı.
- [x] `docker compose up -d --build` uçtan uca doğrulandı: PostgreSQL ve Redis
      healthy, API `/health/detailed` sonucu `db/redis/status = ok`, worker
      ayakta, dashboard backend sağlığını doğru gösteriyor.
- [x] Docker doğrulamasında bulunan altyapı sorunları düzeltildi: boş
      `web/public` dizini, 405 MB `node_modules` build context'i
      (`web/.dockerignore` sonrası 2,1 KB), container içinden yanlış
      `localhost` API çağrısı ve host port çakışmaları için `API_PORT/WEB_PORT`.
- [ ] Coolify'a bağlama + domain + TLS (kullanıcı tarafında yapılacak, talimat verilecek)

### Doğrulanmış kaynak bulguları (bu oturumda gerçek ağ isteğiyle test edildi)

- **KAP liste** (`POST /tr/api/disclosure/members/byCriteria`): çalışıyor,
  `disclosureIndex` alanı üzerinden detaya gidiliyor. `Referer` + `User-Agent`
  zorunlu, teyit edildi.
- **KAP detay** (`GET /tr/api/notification/attachment-detail/{index}`):
  çalışıyor, `disclosure`/`disclosureBody`/`attachments` dönüyor.
- **TEFAS dağılım** (`POST /api/funds/dagilimSiraliGetirT`): dogru govde
  alanlari `fonTipi/fonKodu/basTarih/bitTarih/basSira/bitSira/dil` (camelCase,
  tarih `%Y%m%d`, `basSira`/`bitSira` int) — pytefas kaynağından birebir
  alındı. **Yanıt sarmalayıcısı `{"errorCode","errorMessage","resultList",...}`**
  — `resultList` içindeki satırlar kısaltılmış Türkçe kod isimleriyle geliyor
  (`fonKodu, fonUnvan, tarih, dt, fb, hb, ...` — 50+ alan, çoğu null). Faz 6'da
  bu kısaltmaların (dt=devlet tahvili? fb=?) tam sözlüğü çıkarılmalı.
  ⚠️ **Encoding sorunu tespit edildi:** `fonUnvan` alanı bozuk geliyor
  (`"ATA PORTF�Y..."`) — TEFAS muhtemelen yanlış/eksik charset header'ı
  gönderiyor, Faz 6 collector'ında response encoding'i elle düzeltilmeli
  (muhtemelen `resp.content.decode("iso-8859-9")` veya benzeri denenmeli).
- **RSS** (`bloomberght.com/rss`, `tr.investing.com/rss/news.rss`): ikisi de
  çalışıyor, tahmin doğru çıktı.
- **isyatirimhisse**: `fetch_stock_data(["THYAO"], start, end)` çalışıyor,
  günlük fiyat satırı dönüyor.
- **Windows konsol notu:** `smoke_sources.py` çıktısında Unicode (✓/✗, em-dash)
  kullanma — Windows'un varsayılan `cp1254` konsolu `UnicodeEncodeError`
  veriyor. ASCII (`OK`/`FAIL`, `-`) kullan veya `PYTHONIOENCODING=utf-8` ile
  çalıştır.

## Faz 1 — Hisse Evreni + Fiyat Verisi
✅ Kod ve gerçek PostgreSQL/Docker entegrasyonu doğrulandı

- [x] `Instrument` modeli (`app/models/instrument.py`) — KAP `company/items/IGS/A`
      endpoint'i **bu oturumda keşfedildi ve doğrulandı**: 757 üye, `stockCode`
      alanı temiz ASCII (birincil anahtar), ama `kapMemberTitle`/`cityName`
      alanlarında **kalıcı sunucu taraflı Türkçe karakter bozulması** var
      (U+FFFD — decode hatası değil, KAP'ın kendi verisinde kayıp — bkz. model
      docstring'i). Sadece görüntüleme için kullanılmalı, eşleme mantığı asla
      isme dayanmamalı.
- [x] `PriceDaily` modeli (`app/models/price.py`) — `isyatirimhisse.fetch_stock_data`
      **açılış (open) fiyatı vermiyor**, sadece close/high/low/avg/hacim/PD/USD
      fiyat. Plandaki "o/h/l/c" şeması buna göre revize edildi.
- [x] Alembic migration (`443eb1b2c69d_...py`) — Postgres olmadığı için geçici
      SQLite ile `alembic revision --autogenerate` çalıştırılıp modellerin
      doğruluğu makine tarafından doğrulandı, sonra `server_default` ifadeleri
      Postgres-uyumlu `sa.func.now()`'a düzeltildi.
- [x] `collectors/base.py` — retry (tenacity), rate-limit, Redis'e
      son-başarı/son-hata yazma (`collector:{name}:last_success/last_error` —
      Faz 10 sağlık takibi için hazır altyapı)
- [x] `collectors/instruments.py` — KAP'tan hisse evrenini çekip upsert eder.
      Saf `map_kap_item_to_instrument_fields()` fonksiyonu ayrıştırıldı,
      **6 testle DB'siz doğrulandı** (`tests/test_instrument_mapping.py`).
      Canlı PostgreSQL testi KAP'ın bir şirkette birden çok kodu tek string
      verdiğini yakaladı (`KRDMA, KRDMB, KRDMD`); her kod ayrı satıra açılıyor.
      Aynı KAP OID'sini paylaşabilmeleri için migration `a7e2c4f98b11` eklendi.
- [x] `collectors/prices.py` — `isyatirimhisse`'den EOD fiyat çeker, chunk'lar
      halinde işler (600 hisse × ~0.44 sn/hisse ölçüldü → tam backfill tahmini
      10-15 dk). Saf `map_price_record()` fonksiyonu **5 testle DB'siz
      doğrulandı** (`tests/test_price_mapping.py`)
- [x] `GET /api/instruments`, `GET /api/instruments/{ticker}`,
      `GET /api/instruments/{ticker}/prices` — FastAPI TestClient ile
      wiring doğrulandı (DB gerektirmeyen route'lar gerçekten çalıştırıldı)
- [x] ARQ cron: `collect_instruments` (günde 1, 06:00), `collect_prices`
      (günde 1, 18:30 TRT — BIST kapanışı sonrası)
- [x] `scripts/run_once.py` — manuel/idempotency test CLI'ı
- [x] **Kritik paketleme hatası bulundu ve düzeltildi:** `pyproject.toml`
      setuptools otomatik paket keşfi hem `app` hem `alembic`'i top-level
      paket sanıp hata veriyordu → `[tool.setuptools.packages.find]` ile
      sadece `app*` dahil edildi. Ayrıca `Dockerfile`'da `pip install -e .`
      `COPY . .`'dan ÖNCE çalışıyordu — `app/` henüz image'da yokken paket
      keşfi patlardı. Her ikisi de **yerel venv ile gerçekten test edilerek**
      yakalandı (Docker build'i bekleyecek olsaydı bu ikisi de orada patlardı).
- [x] Hisse collector'ı gerçek Postgres'e karşı iki kez çalıştı: 757 KAP üyesi
      her koşuda 807 ticker'a upsert edildi; tabloda 807/807 benzersiz ticker.
- [x] Fiyat collector'ı `THYAO,ASELS,GARAN --days 30` ile iki kez çalıştı:
      her koşuda 63 satır upsert, DB'de 63/63 benzersiz `(ticker,date)`, hata yok.

### Doğrulanmış bulgular (Faz 1)

- **KAP hisse evreni:** `GET /tr/api/company/items/IGS/A` — `Referer` header'ı
  ile 757 üyeyi tek istekte, sayfalama olmadan döndürüyor. `kapMemberState`
  "A" = aktif.
- **isyatirimhisse timing:** ticker başına ayrı istek atıyor (~0.4-0.5 sn/ticker,
  bu oturumda 3 ve 20 ticker ile ölçüldü). ~600 hisse × 3 yıllık backfill
  büyük ihtimalle 10-15 dk sürecek — ilk `run_once` çağrısını sabırla bekle,
  worker log'unu izle (`chunk_index`/`of` ilerleme logu ekli).
- **Yerel test ortamı:** Python venv `backend/.venv` içinde kuruldu (repo'ya
  gitmiyor). `pip install -e .` çalıştırmadan önce yukarıdaki paketleme
  düzeltmesi şart.

## Faz 2 — KAP Toplayıcı
✅ Kod ve gerçek PostgreSQL/Docker idempotency akışı doğrulandı

- [x] `KapDisclosure` + `KapAttachment` modelleri — bildirim numarası ve KAP
      `objId` doğal anahtar; ham liste/detay JSON'u, görünür Türkçe metin,
      dosya hash/boyut/hata bilgisi saklanıyor. Ek içeriği `deferred BYTEA`.
- [x] Alembic migration (`9c1f0d4a2e73_...py`) — ticker JSONB alanı için GIN
      indeks dahil; `alembic upgrade head --sql` ile PostgreSQL DDL üretimi
      doğrulandı.
- [x] `collectors/kap.py` — tarih penceresini **gün gün** sorgular (KAP'ın
      istek başına 2000 sınırında geniş aralık veri kaybetmesin), listeyi
      `disclosure_index` ile upsert eder, yalnızca yeni/eksik detayları çeker.
- [x] KAP HTML'inden gizli İngilizce hücreleri atıp görünür Türkçe metin
      çıkaran stdlib parser eklendi; ham HTML ayrıca korunuyor.
- [x] KAP ekleri: `objId/fileName/fileExtension` şeması gerçek ekli bildirimle
      doğrulandı. Java-serialized `byte[]` sarmalayıcı uzunluk kontrolüyle
      çözülüyor; kaynak ileride ham dosyaya geçerse geriye uyumlu.
- [x] Gerçek ek doğrulaması: KAP bildirim `1659248`, objId
      `4028328d9f52dddd01a06d943dc11178`; 2.699.462 bayt sarmalayıcıdan
      2.699.435 bayt `%PDF-1.4` çıktı başarıyla elde edildi (fixture'a büyük
      binary eklenmedi).
- [x] Idempotency: ilk çalışmada yeni detay alınır; ikinci çalışmada `new=0`
      ve aynı detay için yeni ağ isteği yapılmaz. İndirilemeyen ekler sonraki
      koşuda yeniden denenir.
- [x] ARQ `collect_kap` işi (5 dakikada bir) + manuel CLI:
      `python -m scripts.run_once kap --days 3 [--no-attachments]`.
- [x] API: `GET /api/disclosures`, `GET /api/disclosures/{index}`,
      `GET /api/disclosures/{index}/attachments/{obj_id}`; ticker/class
      filtresi ve cursor/limit desteği.
- [x] Fixture tabanlı parser + idempotency testleri dahil **26/26 test geçti**;
      değiştirilen dosyalarda Ruff temiz; OpenAPI route kaydı doğrulandı.
- [x] `alembic upgrade head` gerçek PostgreSQL üzerinde çalıştı; güncel head
      `a7e2c4f98b11`.
- [x] Üç günlük canlı KAP koşusu x2: ilk koşu 293 yeni bildirim/293 detay,
      ikinci koşu `new=0`, `details_fetched=0`. DB'de 293 bildirim ve 124 ek
      metadata satırında tekrar yok. 15:25 cron'u kalan 18 eki de başarıyla
      tamamladı (`attachment_failures=0`); 124/124 içerik indirildi. API'den
      örnek dosya `%PDF-1.4` byte imzasıyla doğrulandı.

## Faz 3 — Haber Toplayıcı
✅ Kod ve gerçek PostgreSQL/Docker idempotency akışı doğrulandı

- [x] `NewsArticle` modeli + Alembic migration (`d3f6a81c2e90`): kaynak,
      canonical URL/SHA-256 doğal anahtar, başlık/özet/yazar/görsel, UTC yayın
      zamanı, ticker kodları ve ham RSS satırı saklanıyor; ticker JSONB alanında
      GIN indeks var.
- [x] Bloomberg HT ve Investing.com.tr RSS kaynakları ortak `NewsCollector`
      içinde toplanıyor. Kaynaklardan biri geçici olarak bozulursa diğeri devam
      ediyor; tüm kaynaklar bozulursa koşu başarısız sayılıyor.
- [x] URL canonicalization takip parametrelerini/fragment'i atıyor, host ve
      query sırasını normalize ediyor. Aynı makale `url_hash` üzerinden upsert
      edildiği için tekrar satır oluşmuyor.
- [x] Yayın zamanları timezone-aware UTC saklanıyor. Bloomberg HT offset'i
      doğrudan kullanılıyor; Investing'in offset'siz RSS saati resmi makale
      sayfasındaki TRT gösterimiyle karşılaştırılarak UTC olduğu doğrulandı.
- [x] Ticker eşlemesi yalnızca aktif `instrument` evrenindeki, başlık/özette
      büyük harfle açıkça yazılmış veya URL token'ı olarak geçen kodlarla
      yapılıyor; şirket isminden bulanık tahmin yapılmıyor.
- [x] API: `GET /api/news`, `GET /api/news/{id}`; source/ticker/cursor/limit
      filtreleri ve yayın zamanına göre deterministik sıralama.
- [x] ARQ `collect_news` işi 5 dakikada bir, KAP'tan 30 saniye gecikmeli;
      manuel CLI: `python -m scripts.run_once news`.
- [x] Gerçek Docker/PostgreSQL koşusu x2: ilk koşu 30 yeni haber, ikinci koşu
      `new=0`; DB'de 30 satır/30 benzersiz URL hash (Bloomberg HT 20,
      Investing 10). API liste/kaynak filtresi ve 404 davranışı doğrulandı.
- [x] Fixture tabanlı URL/tarih/ticker/RSS testleri dahil Docker içinde
      **34/34 test geçti**; Ruff ve PostgreSQL migration DDL kontrolü temiz.

## Faz 4 — LLM Değerlendirme Katmanı
🔶 Kod ve Docker entegrasyonu tamam; canlı Gemini çağrısı API anahtarı bekliyor

- [x] `LlmEvaluation` modeli + `f47a1c8d6b20` migration'ı: haber/KAP kaynak
      kimliği, içerik hash'i, prompt/model/tier bazlı deterministik anahtar,
      Tier 1→Tier 2 parent zinciri, skorlar, yapılandırılmış/ham çıktı, hata,
      deneme sayısı, latency ve token kullanımı saklanıyor.
- [x] Promptlar repo içinde sürümlü `app/llm/prompts/v1.md` dosyasında; kaynak
      metni güvenilmeyen veri kabul ediliyor, delimiter enjeksiyonu kaçışlanıyor
      ve çıktı yatırım tavsiyesi/al-sat emri üretmeyecek şekilde sınırlandırılıyor.
- [x] Resmi `google-genai` SDK eklendi. Tier 1 `gemini-3.7-flash` + düşük
      thinking, Tier 2 geçerli endpoint `gemini-3.1-pro-preview` + orta thinking;
      Pydantic/JSON Schema ile yapılandırılmış çıktı kullanılıyor.
- [x] Maliyet kapıları: `LLM_ENABLED=false` güvenli varsayılanı, günlük input /
      output token limitleri, batch sınırı ve kaynak metni boyut sınırı.
- [x] Tier 2 yalnız Tier 1'in ilgili (>=60), yüksek etkili (varsayılan >=70),
      derin analiz istediği ve aktif BIST ticker'ı taşıdığı kayıtlarda açılıyor.
      Modelin uydurduğu/aktif olmayan ticker kodları saklanmadan eleniyor.
- [x] Backlog açlığı önlendi: hiç değerlendirilmemiş eski kaynaklar, başarısız
      işler ve 30 dakikadan uzun `running` kalan işler ayrı SQL seçimleriyle
      kuyruğa geri geliyor; en fazla üç deneme yapılıyor.
- [x] API: `GET /api/evaluations`, `GET /api/evaluations/{id}`; kaynak, source
      id, ticker, tier, durum, cursor ve limit filtreleri.
- [x] ARQ değerlendirme işi 10 dakikada bir; `python -m scripts.run_once llm`
      CLI komutu. Kapalı durumda worker gerçekten ücretli çağrı yapmadan dönüyor.
- [x] Gerçek PostgreSQL + sahte Gemini geçidi: Tier 1 ve Tier 2 ilk çağrıda iki
      bağlı satır oluşturdu, ikinci çağrılar `skipped`; tokenlar kaydedildi,
      ticker filtresi çalıştı ve geçici test satırları temizlendi.
- [x] Docker içinde **45/45 test geçti**; Ruff, OpenAPI, Alembic head/check,
      API liste/404 ve worker cron kaydı doğrulandı.
- [ ] `GEMINI_API_KEY` sağlanıp kontrollü küçük batch ile gerçek Gemini çağrısı
      ve kullanım metadata'sı doğrulanacak; o zamana kadar `LLM_ENABLED=false`.

## Faz 5 — Temel Analiz Motoru
✅ Kod ve gerçek PostgreSQL/Docker idempotency akışı doğrulandı

- [x] `FinancialFact` + `FundamentalSnapshot` modelleri ve
      `a91e5c7d3f42` migration'ı: ham finansal kalemler kaynak koduyla;
      hesaplanmış oranlar, bileşen skorları ve veri tamlığı ayrı snapshot'ta
      tutuluyor. Doğal anahtarlar tekrar satırı engelliyor.
- [x] İş Yatırım `MaliTablo` uç noktası gerçek THYAO yanıtıyla doğrulandı.
      Collector `XI_29`, `UFRS`, `UFRS_K` gruplarını sırayla keşfediyor;
      3/6/9/12 aylık kümülatif ve bilanço anlık değerlerini kaynak `itemCode`
      alanlarıyla eşliyor.
- [x] Gelir/net kâr yıllık büyümesi; brüt, faaliyet ve net marj; cari oran;
      borç/özsermaye; nakit/borç; yıllıklandırılmış ROE; faaliyet ve serbest
      nakit akışı marjları deterministik hesaplanıyor.
- [x] 0-100 temel skor büyüme, kârlılık, bilanço ve nakit akışı bileşenlerinin
      açık eşiklerle hesaplanan teknik bir sıralama sezgisidir; yatırım
      tavsiyesi değildir. Yetersiz veride skor üretilmiyor.
- [x] Otomatik aday evreni son 30 gündeki ilgili LLM sonuçlarından en fazla 50
      aktif BIST koduyla sınırlı. Manuel CLI açık ticker/yıl aralığını kabul
      ediyor: `python -m scripts.run_once fundamentals --tickers THYAO
      --start-year 2025 --end-year 2026`.
- [x] API: `GET /api/fundamentals/{ticker}` ve
      `GET /api/fundamentals/{ticker}/facts`; yıl, geçerli dönem ve kalem kodu
      filtreleri. ARQ işi her gün 07:00'de instrument yenilemesinden sonra.
- [x] Gerçek THYAO fixture'ı ve mapping/oran/turnaround/hatalı yanıt testleri
      eklendi. Docker içinde **52/52 test geçti**; Ruff ve Alembic check temiz.
- [x] Canlı Docker/PostgreSQL koşusu x2: ilk koşu 880 yeni benzersiz finansal
      gerçek ve 6 snapshot oluşturdu; ikinci koşu `new=0`. DB'de 880/880 doğal
      anahtar benzersiz, API son snapshot ve ham `3C` satış kalemini döndürdü.

## Faz 6 — Analist Tavsiyeleri + Fon Akımları + Konsensüs
⬜ Başlanmadı

## Faz 7 — Bileşik Skor + Sinyal Motoru
⬜ Başlanmadı

## Faz 8 — Paper Portföy Motoru
⬜ Başlanmadı

## Faz 9 — Next.js Dashboard
⬜ Başlanmadı

## Faz 10 — Alarm + Gözlemlenebilirlik
⬜ Başlanmadı

## Faz 11 — Değerlendirme / Backtest
⬜ Başlanmadı

---

## Bilinen riskler / açık sorular

- Frontend build'i geçiyor; ancak `npm install` mevcut Next.js 15.0.3 için
  güvenlik uyarısı ve toplam 2 high + 1 critical bağımlılık bulgusu verdi.
  Production deploy öncesi ayrı bir bağımlılık güncelleme/regresyon işi şart.
- KAP'ın ek sunucusu uzun canlı koşuda zaman zaman bağlantıyı yanıt vermeden
  kapattı. Retry politikası ve batch toleransı çalıştı; ikinci koşuda 24 eksik
  ekin 6'sı, sonraki 5 dakikalık cron'da kalan 18'in tamamı indirildi.
- KAP ekleri şimdilik PostgreSQL `BYTEA` içinde saklanıyor. İlk kullanım için
  basit ve yedeklenebilir; veri büyüdüğünde Faz 10 öncesi retention veya S3
  uyumlu nesne depolama kararı verilmeli.
- KAP'ın günlük 2000 kayıt sınırı dolarsa collector sessiz veri kaybetmek
  yerine hata verir. Böyle bir gün görülürse üye/kategori bazında bölme
  stratejisi eklenmeli.
