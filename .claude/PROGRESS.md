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
- [x] **2026-09-08 kaynak genişletmesi:** AA Ekonomi (resmi Anadolu Ajansı),
      Dünya Gazetesi ve Foreks/ForInvest (özel finans/piyasa telgrafı) eklendi
      — toplam 5 RSS kaynağı. Üçü de pubDate'te açık UTC offset taşıyor,
      naive_timezone fallback'i gerekmiyor. Gerçek yanıtlar fixture'a
      kaydedildi (Foreks 100 gerçek satırdan ilk 15'ine küçültüldü), 3 yeni
      mapping testiyle doğrulandı (**123/123 test** yeşil). `/haberler`
      ekranındaki kaynak filtreleri ve `sourceName()` etiketleri güncellendi.
      Canlı Docker koşusu x2: ilk koşu 5/5 kaynak başarılı, 185 listelendi,
      156 yeni; ikinci koşu `new=0`. Her 5 kaynaktan da en az bir satır
      `GET /api/news?source=...` ile doğrulandı; `/haberler?source=foreks`
      HTTP 200 ve doğru filtre etiketleriyle render edildi.

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
✅ Çekirdek akış + kurum PDF hattı; Docker/PostgreSQL/Redis'te canlı doğrulandı

- [x] `AnalystRecommendation` + günlük `AnalystConsensus` modelleri ve
      `c62f1a8e4d73` migration'ı: kaynak/kurum/tarih/hedef/tavsiye geçmişi,
      kurum bazında son görüş, hedef dağılımı ve 0-100 görüş skoru saklanıyor.
- [x] Doğrudan kurumsal kaynak olarak İş Yatırım takip listesi ve çok-kurumlu
      agregatör olarak Halka Arz Takvimi ayrı parser/sağlık takibiyle bağlandı.
      AL/TUT/SAT, endekse göre görüşler ve gözden geçiriliyor ortak sözlüğe
      normalize ediliyor; aynı kurum iki kaynakta varsa en güncel, eşit tarihte
      doğrudan kurumsal kayıt kazanıyor.
- [x] `FundSnapshot` + `FundFlowAggregate`: TEFAS resmi genel bilgi ve portföy
      dağılımı JSON uçları fon/tarih bazında birleştiriliyor. Net fon akımı,
      AUM değişiminden birim fiyat getiri etkisi çıkarılarak tahmin ediliyor;
      güncel yurtiçi hisse ağırlığıyla tahmini hisse akımı hesaplanıyor.
- [x] API: analist geçmişi/konsensüsü, fon snapshot geçmişi ve günlük fon akım
      agregaları. ARQ analist işi 07:30, TEFAS işi 20:00; manuel `analysts` ve
      `fund-flows --fund-kind YAT --days 7` komutları.
- [x] İki analist HTML kaynağı ve iki fon/iki gün TEFAS JSON'u gerçek fixture
      olarak eklendi. Docker içinde **58/58 test geçti**; Ruff ve Alembic check
      temiz, worker 17 fonksiyonla başladı.
- [x] Canlı analist koşusu x2: 427 kabul edilen görüş, 90 ticker konsensüsü;
      ikinci koşu `new=0`. THYAO konsensüsü 9 ayrı kurum üzerinden API'de
      doğrulandı.
- [x] Canlı TEFAS YAT koşusu x2: 10.202 snapshot, 10.037 dağılım eşleşmesi ve 5
      işlem günü agregası; ikinci koşu `new=0`. DB'de 10.202/10.202 doğal anahtar
      benzersiz.
- [x] Kurum PDF hattı (`collectors/institutional_reports.py`): PhillipCapital
      Türkiye'nin `arastirma-urunleri` sayfası — login gerektirmeyen, sunucu
      tarafında render edilen tek arac kurum arşivi olarak bu oturumda
      araştırıldı ve doğrulandı (İş Yatırım/Ak Yatırım/Oyak/QNB Finansinvest/
      Tacirler/Şeker gibi diğerleri üyelik duvarı veya JS-SPA arkasında).
      Şirket Raporları kategorisi keşfedilip (sayfalama + azalan tarih sıralı
      erken durma) PDF indiriliyor, `pdftotext -layout` (poppler-utils) ile
      sayfa 1 metne çevrilip "Bloomberg Ticker" çapasından sonraki pencerede
      hedef fiyat/referans fiyat/getiri potansiyeli/öneri etiketleri
      ayrıştırılıyor. GUID → `source_key`, checksum (`pdf_sha256`) `raw_data`
      JSONB'de. Aynı `AnalystRecommendation`/`AnalystConsensus` şeması ve
      `recompute_analyst_consensus()` (analysts.py'den ortak fonksiyona
      çıkarıldı) yeniden kullanıldı — yeni migration gerekmedi.
- [x] Sablon tutarsızlığı: raporların ~%15'i ("Bloomberg Ticker" içeren yeni
      şablon) güvenilir ayrıştırılabiliyor; "Toplantı Notu" ve eski kapak
      şablonları yapısal hedef fiyat tablosu taşımıyor — isme dayalı tahmin
      YAPILMADAN sessizce atlanıyor (proje kuralına uygun, sadece kod eşlemesi).
- [x] Redis tabanlı atlama önbelleği (`institutional_reports:skipped_guids`):
      ayrıştırılamayan/aktif olmayan tickera düşen PDF'ler DB'ye hiç
      yazılmadığı için önbellek olmadan her koşuda tekrar indirilip
      ayrıştırılıyorlardı — bu oturumda canlı testte yakalanıp düzeltildi.
- [x] Docker imajına `poppler-utils` eklendi (`pdftotext` için). Docker içinde
      **65/65 test geçti** (9 yeni: 4 gerçek PDF şablonu — TR/EN/nokta-ondalık/
      atlama senaryosu — + liste HTML + tarih/GUID ayrıştırma); Ruff temiz.
- [x] Canlı PhillipCapital koşusu x3: ilk koşu (2 sayfa sınırlı) 20 keşif/3
      kabul, ikinci koşu (önbellek düzeltmesi öncesi) `new=17` bulup **collector
      idempotency hatasını ortaya çıkardı**, düzeltme sonrası üçüncü koşu
      sadece sayfa 1'i kontrol edip `new=0` döndü (sayfalama erken durması
      çalışıyor). Tam geri dolum: 138 rapor keşfedildi, 21 kabul edildi, 114
      şablon uyumsuzluğu nedeniyle atlandı, 0 indirme hatası; tekrar
      koşuda `new=0`. DB'de 24/24 `source_key` benzersiz (bazı raporların
      TR/EN ayrı PDF'leri var, ikisi de ayrı meşru kayıt). GRSEL konsensüsü
      API'de `source_breakdown: {"phillipcapital_pdf": 1}` ile doğrulandı.

## Faz 7 — Bileşik Skor + Sinyal Motoru
✅ Kod, API, worker ve gerçek PostgreSQL idempotency akışı doğrulandı

- [x] `CompositeSignalSnapshot` modeli ve `e84b2b3d91f0` migration'ı: ticker/gün/
      model sürümü doğal anahtarı, 0-100 skor, teknik görünüm etiketi, güven,
      kapsam, bileşen puanları/etkin ağırlıklar ve kaynak kanıtları saklanıyor.
- [x] Sürümlü V1 motoru: AI `%35`, temel analiz `%30`, analist konsensüsü `%25`,
      TEFAS piyasa akımı `%10`. Eksik kaynak sıfır sayılmıyor; mevcut ağırlıklar
      yeniden normalize ediliyor ve en az iki bileşen olmadan skor yayımlanmıyor.
- [x] LLM tarafında aynı kaynak belgesinin Tier 2 sonucu Tier 1'e tercih ediliyor;
      duygu × etki × ilgi, güven ve üç günlük yarı ömürlü tazelikle birleştiriliyor.
      Analist oyu hedef potansiyeliyle, fon akımı büyüklüğü piyasa genişliğiyle
      beraber puanlanıyor.
- [x] API: `GET /api/signals` (tarih/ticker/etiket/minimum skor filtreleri) ve
      `GET /api/signals/{ticker}` geçmişi. CLI: `python -m scripts.run_once signals`.
      Worker LLM işinden sonra her 10 dakikada bir skorları tazeliyor.
- [x] Saf skor/esik/eksik veri/Tier 2/regresyon testleri dahil **72/72 test geçti**;
      Ruff, production web build ve offline PostgreSQL DDL üretimi temiz.
- [x] Gerçek PostgreSQL koşusu: 91 adaydan 88 snapshot, 3 düşük kapsam nedeniyle
      atlandı. Tekrar koşuları `new=0`, `updated=88`; migration head ve API
      sıralama/ticker geçmişi canlı doğrulandı.

## Faz 8 — Paper Portföy Motoru
✅ Kod, API, worker, arayüz ve gerçek PostgreSQL idempotency akışı doğrulandı

- [x] Long-only ve kaldıraçsız `paper-v1` stratejisi: 1.000.000 TL sanal
      başlangıç bakiyesi, en fazla 10 pozisyon, pozisyon başına en fazla `%10`
      portföy ağırlığı ve tam adetli işlemler.
- [x] Giriş kapıları bileşik skor `>=75`, güven `>=0,25` ve en az iki bileşen;
      çıkış kapısı skor `<40`. Yalnızca en fazla yedi günlük EOD fiyatı kullanılır.
- [x] Alış/satışlarda `%0,10` komisyon ve `%0,05` fiyat kayması; minimum işlem
      değeri 1.000 TL. Canlı aracı kurum veya emir bağlantısı yoktur.
- [x] Portföy, açık pozisyon, işlem defteri ve günlük performans snapshot modelleri;
      `f95c4a21d8e7` migration'ı. Gün/portföy/ticker/yön/strateji sürümünden türetilen
      benzersiz execution key aynı emrin yeniden yazılmasını engeller.
- [x] API: portföy listesi/detayı, pozisyonlar, işlem geçmişi ve performans serisi.
      CLI: `python -m scripts.run_once paper`; worker her işlem günü 18:46'da,
      sinyal motorundan sonra portföyü günceller.
- [x] `/portfoy` ekranı: toplam değer, nakit, K/Z ve komisyon özetleri; performans
      grafiği, açık pozisyon tablosu ve son işlemler. Merkezi tema tokenlarını kullanır.
- [x] Saf emir planlama, eşik, sıralama, execution key ve route testleriyle toplam
      **78/78 test geçti**; Ruff, production web build ve offline PostgreSQL DDL temiz.
- [x] Canlı Docker/PostgreSQL: migration head `f95c4a21d8e7`; 10 aday için 200 EOD
      fiyatı tamamlandı. İlk koşu 10 alış/10 pozisyon, ikinci koşu 0 yeni işlem;
      DB'de 10 işlem/10 benzersiz key. İlk snapshot 998.502,40 TL (`-%0,1498`),
      başlangıç farkı yalnızca modellenen komisyon ve fiyat kaymasından oluşuyor.

## Faz 9 — Next.js Dashboard
✅ Mevcut Faz 1-8 özellikleri için responsive arayüz tamamlandı

- [x] Genel bakış, piyasalar/hisse detayı, haber, KAP, AI analizleri, kurumsal
      veriler ve bileşik sinyal sıralaması; detay ekranları ve sayfalama.
- [x] Renkler `web/src/app/globals.css` içindeki tek tema token bloğundan yönetiliyor.
- [x] Bileşik skor sıralaması dashboard ve hisse detayına bağlandı; production
      Docker build ve ana rotalar canlı veriyle HTTP 200 doğrulandı.
- [x] Paper portföy ekranı performans/pozisyon/işlem API'lerine bağlandı;
      `/portfoy` çalışan Docker servisi üzerinden HTTP 200 doğrulandı.
- [x] Hisse detay sayfası fiyat, geniş finansal metrikler, bileşik sinyal,
      analist konsensüsü/görüşleri, ilgili haberler, KAP bildirimleri, AI
      değerlendirmeleri, paper pozisyon/işlemler ve makro faiz ortamını tek
      ekranda birleştiriyor; uzun sayfa için bölüm kısayolları eklendi.
- [x] Neon sarı ana vurgu, merkezi tema bloğunda sakin mavi (`#7fa6e8`)
      palete çevrildi; tüm sayfalar ek değişiklik olmadan yeni rengi kullanıyor.

## Faz 10 — Alarm + Gözlemlenebilirlik
🔶 Çekirdek sağlık ve alarm katmanı tamam; genişletiliyor

- [x] `/health/detailed`: PostgreSQL/Redis yanında sekiz collector'ın son başarı,
      son hata ve kaynak türüne göre tazelik durumunu raporluyor.
- [x] ARQ worker heartbeat'i Redis'e yazılıyor; eksik, hatalı ve gecikmiş
      bileşenler ortak sağlık raporunda ayrıştırılıyor.
- [x] Collector hataları ve periyodik tazelik kontrolü, `N8N_WEBHOOK_URL`
      tanımlıysa yapılandırılmış webhook alarmı gönderiyor. Aynı alarm için
      varsayılan bir saatlik Redis cooldown mükerrer bildirimleri engelliyor.
- [x] `/sistem` ekranı altyapı bağlantılarını, worker'ı ve veri hatlarını
      profesyonel durum görünümüyle gösteriyor.
- [x] Tazelik/hata/ilk çalışma durumları ve webhook dedup testleri dahil toplam
      **91/91 test geçti**; Ruff ve production web build temiz.
- [ ] Canlı N8N URL'si sağlandığında kontrollü test alarmı uçtan uca doğrulanacak.

## Ek Özellik — TCMB Faiz Kararları + Piyasa Etkisi
✅ Resmî kaynak, API, worker, arayüz ve idempotency akışı doğrulandı

- [x] Resmî TCMB PPK yıl/takvim sayfaları doğrudan okunuyor; geçmiş karar
      bağlantıları ile yaklaşan bağlantısız toplantı tarihleri ayrıştırılıyor.
- [x] Karar metninden politika faizi, önceki oran, baz puan değişimi, gecelik
      borç verme/borçlanma koridoru, karar özeti ve yönlendirme çıkarılıyor.
- [x] Politika faizi HIKE/CUT/HOLD ayrımı yalnız bir hafta vadeli repo oranına
      göre yapılıyor; koridordaki tekil değişiklik yanlışlıkla faiz artışı sayılmıyor.
- [x] Hisse, banka, gayrimenkul, TL ve tahvil aktarım kanalları için açıkça
      “kural tabanlı senaryo” olarak etiketlenen etki açıklamaları var; gerçekleşmiş
      getiri veya yatırım tavsiyesi iddiası yok.
- [x] `b7d4e9a2c610` migration'ı, `/api/macro/policy-decisions`, günlük 06:30
      worker işi, `tcmb-policy [--years ...] [--refresh]` CLI komutu ve `/makro`
      ekranı eklendi.
- [x] Canlı TCMB 2025-2026 koşusu: 17 tarih, 14 yayımlanmış karar, 3 yaklaşan
      toplantı. İkinci koşu `new=0`, `details_fetched=0`; canlı API ve `/makro`
      ekranı HTTP 200. Gerçek kaynak fixture testleri dahil toplam 91 test geçti.

## Faz 11 — Tarama Takvimi Yönetimi
✅ PostgreSQL, Redis worker, yönetim API'si ve `/sistem` arayüzü tamamlandı

- [x] `/sistem` ekranında her veri hattının etkin çalışma aralığını, son çalışma
      zamanını, son sonucu ve hesaplanan bir sonraki çalışma zamanını göster.
- [x] Haber taramasının mevcut varsayılanını (5 dakika), KAP/LLM/sinyal ve diğer
      collector takvimleriyle birlikte tek yönetim ekranından değiştirilebilir yap.
- [x] Ayarları PostgreSQL'de migration ile oluşturulan `collector_schedule`
      tablosunda sakla; container yeniden başladığında seçimler kaybolmasın.
- [x] Etkinleştir/duraklat, “şimdi çalıştır” ve dakika/saat/gün bazlı aralık
      işlemleri için doğrulamalı yönetim API'si ekle. Çok sık istekleri önlemek
      için collector bazlı güvenli alt sınırlar tanımla.
- [x] Statik ARQ cron listesini, veritabanındaki etkin ayarları okuyabilen dinamik
      tetikleyiciye taşı; birden fazla worker çalıştığında Redis kilidi ve mevcut
      idempotency kuralları aynı işin iki kez çalışmasını engellesin.
- [x] Takvim değişiklikleri ve elle çalıştırmalar için aktör/zaman/eski-yeni
      değer içeren audit kaydı tut; yönetim uçlarını kimlik doğrulama ile koru.
- [x] Europe/Istanbul saat dilimini arayüzde açık göster; worker içinde UTC ile
      güvenli dönüşüm yap ve yaz/kış saati varsayımlarını test et.
- [x] API, worker ve web testlerine ek olarak Docker yeniden başlatma sonrası
      ayar kalıcılığı ve çoklu-worker yarış testi ekle.
- [x] `c4e8a2b1d730` migration head'i, 12 varsayılan takvim, otomatik ve manuel
      Redis enqueue akışları canlı Docker/PostgreSQL üzerinde doğrulandı. Haber
      ayarı 5→10→duraklat→5 ve ayrıca 5→7→container recreate→7→5 akışlarında
      doğru kaldı. Ruff, production web build ve toplam **99/99 test** temiz.

## Faz 12 — Gelişmiş Hisse Grafikleri
✅ Etkileşimli fiyat, hacim ve teknik gösterge grafiği tamamlandı

- [x] Mevcut 90 günlük kapanış çizgisini 1A/3A/6A/1Y/3Y/Tümü aralıkları,
      tooltip, crosshair, yakınlaştırma ve mobil kullanımla geliştir.
- [x] Fiyatın altında TL işlem hacmini; grafikte günlük en düşük/en yüksek ve
      ağırlıklı ortalama fiyatı göster. Eksik değerleri açıkça belirt.
- [x] MA20/MA50, RSI(14), dönem değişimi ve dönem düşük/yüksek değerlerini
      açılıp kapanabilir katmanlar ve özet metrikler halinde ekle.
- [x] Mum grafik için `open` verisi sağlayan güvenilir ve lisans açısından uygun
      kaynak ayrıca doğrulanmadan sahte OHLC üretme; mevcut kaynak yalnız
      kapanış/minimum/maksimum/AOF/hacim sağlıyor.
- [x] Mevcut indeksli başlangıç/bitiş tarihi API'si üzerinden tüm mevcut geçmişi
      bir kez yükle; aralık geçişlerini tekrar ağ isteği olmadan tarayıcıda yap.
- [x] Boş/yetersiz veri koruması, erişilebilir SVG etiketi ve touch-safe etkileşim
      ekle; production build ile masaüstü ve 390px mobil görünümü doğrula.
- [x] Canlı `/piyasalar/THYAO` gerçek 21 işlem günlük fiyat/hacim verisiyle HTTP
      200 döndü ve görsel kontrolden geçti. Yeni/eksik veri uydurulmuyor; üç yıllık
      collector backfill'i geldikçe uzun aralıklar otomatik genişliyor.

## Faz 13 — Docker / Coolify Üretim Hazırlığı
✅ Kod ve yerel üretim provası tamamlandı; gerçek domain/TLS bağlantısı kullanıcıda

- [x] Yeni özelliklerin tamamı PostgreSQL + Redis üzerinde çalışsın; container
      içine yazılan yerel dosya veya SQLite üretim bağımlılığı oluşmasın.
- [x] PostgreSQL kalıcı volume, yedekleme ve geri yükleme prosedürünü; migration
      sırası ve geri alma adımlarını Coolify dağıtım dokümanında doğrula.
- [x] `api`, `worker` ve `web` stateless kalacak şekilde Compose/Coolify health
      check, restart policy, resource limit ve servis bağımlılıklarını sertleştir.
- [x] Yalnız web/API'yi dışarı aç; PostgreSQL ve Redis'i private network'te tut.
      `DATABASE_URL` ile Coolify managed/external PostgreSQL kullanımını da destekle.
- [x] Domain, HTTPS, CORS, secret/env yönetimi, worker ölçekleme ve saat dilimi
      ayarları için production `.env` kontrol listesi hazırla.
- [x] Temiz veritabanından deploy, migration, seed/collector, restart-persistence,
      `/health/detailed` ve ana ekranları kapsayan uçtan uca Coolify smoke testi yap.

- [x] Temiz isimlendirilmiş Compose projesi sıfır volume ile kuruldu; migration head
      `c4e8a2b1d730` ve 12 varsayılan takvim doğrulandı, sonra test kaynakları kaldırıldı.
- [x] Gerçek PostgreSQL özel-format yedeği alındı; ayrı PostgreSQL 16 container'ına
      şema ve seçili tablolar geri yüklenerek migration sürümü ve 12 takvim doğrulandı.
- [x] API/worker `tradeai`, web `node` kullanıcısıyla çalışıyor; uygulama dosya
      sistemleri salt-okunur, yalnız `/tmp` ve Next cache tmpfs. Redis AOF etkin.
- [x] Tarayıcıdaki KAP ek indirmeleri public API domainine bağlı kalmadan, kimlik
      doğrulamalı path ve header aktarımıyla web'in same-origin proxy'sine taşındı.
- [x] CORS/Host güvenlik testleri, production smoke, Next.js 16 build, `npm audit`
      (0 bulgu), Ruff ve toplam **102/102 test** temiz.
- [x] **2026-09-08 eklendi:** `.github/workflows/ci.yml` — her push/PR'da backend
      (`ruff check`, `pytest`, `alembic upgrade head --sql` ile DB'siz offline DDL
      kontrolü) ve web (`tsc --noEmit`, `next build`) otomatik çalışıyor. Önceden
      bunların hepsi elle çalıştırılıyordu.

## Faz 14 — Değerlendirme / Backtest
✅ Kod, testler, production build ve gerçek Docker/PostgreSQL akışı doğrulandı

- [x] Bilesik sinyalleri, sinyal tarihinden sonraki ilk mevcut EOD kapanisinda
      uygulayan; komisyon, kayma, nakit ve pozisyon limitlerini hesaba katan
      deterministik backtest motoru ekle.
- [x] Tarih araligi/strateji ayarlariyla calistirma, sonucu PostgreSQL'de saklama
      ve gecmis kosulari listeleme API'lerini ekle.
- [x] Getiri, maksimum dusus, oynaklik, Sharpe, islem/kazanma orani ve toplam
      maliyet metriklerini; varsayimlariyla birlikte `/backtest` ekraninda goster.
- [x] Yetersiz veri ve sinyal sonrasi fiyat bulunamama durumlarini acikla; gercek
      endeks verisi olmadan temsili benchmark veya sonuc uydurma.
- [x] Birim/API testleri, production build ve Docker smoke testiyle dogrula.
      Motor testleri (giris/cikis filtreleri, gecikmis/kayip fiyat atlama,
      acik pozisyon mark-to-market, ucret/kayma/drawdown/Sharpe, bos veri seti,
      gecersiz config) ve API sozlesme testleri (route kaydi, varsayilan/gecersiz
      istek, durum hesaplama) dahil **117/117 test** (backend geneli) yesil;
      degisen dosyalarda Ruff temiz. Web production build (`next build`,
      Turbopack) hatasiz tamamlandi, `/backtest` route derlendi.
      Canli Docker/PostgreSQL kosusu: `POST /api/backtests` gercek
      `composite_signal_snapshot` (176 sinyal) ve `price_daily` (351 fiyat)
      verisiyle calisti, `backtest_run/_point/_trade` tablolarina yazdi;
      EOD fiyat toplayicisi o an `pending` oldugundan sinyal sonrasi fiyat
      bulunamayip `status=INSUFFICIENT_DATA` dondu — bu, motorun veri
      uydurmadan dogru sekilde raporladigi beklenen davranis. `GET
      /api/backtests` listesi, `GET /api/backtests/{id}` detayi ve bulunamayan
      id icin 404 canli API'de dogrulandi; `/backtest` ekrani gercek calisan
      web container'inda HTTP 200 ve kosunun tarih/metrik verisiyle rendered.

---

## Bilinen riskler / açık sorular

- Frontend Next.js 16.3.4 ve React 19.2.8'e yükseltildi; kilit dosyası eklendi,
  temiz production build ve `npm audit` 0 bulguyla doğrulandı.
- KAP'ın ek sunucusu uzun canlı koşuda zaman zaman bağlantıyı yanıt vermeden
  kapattı. Retry politikası ve batch toleransı çalıştı; ikinci koşuda 24 eksik
  ekin 6'sı, sonraki 5 dakikalık cron'da kalan 18'in tamamı indirildi.
- KAP ekleri şimdilik PostgreSQL `BYTEA` içinde saklanıyor. İlk kullanım için
  basit ve yedeklenebilir; veri büyüdüğünde Faz 10 öncesi retention veya S3
  uyumlu nesne depolama kararı verilmeli.
- ~~KAP'ın günlük 2000 kayıt sınırı dolarsa collector sessiz veri kaybetmek
  yerine hata verir.~~ **2026-09-08 düzeltildi:** bir günün sorgusu limite
  çarparsa collector artık hata vermeden önce aktif `instrument.kap_member_oid`
  evrenini 150'lik parçalara bölüp aynı günü parça parça yeniden sorguluyor
  (`KapCollector._fetch_day`), sonuçları birleştiriyor. Yalnızca bölünmüş bir
  parça da limite çarparsa (gerçekçi değil ama teorik olarak mümkün) hâlâ
  açıkça hata veriyor — sessiz veri kaybı yok. 4 yeni testle doğrulandı
  (`tests/test_kap_collector_idempotency.py`); canlı KAP API'sine karşı normal
  (bölünmemiş) yol 3 günlük gerçek koşuda hatasız çalıştı (244 bildirim,
  `new=0`, idempotency bozulmadı).
- 2026-09-08 canlı kontrolde `trade.furkantahabademci.com.tr` HTTPS ve web health
  başarılı; `api.trade.furkantahabademci.com.tr` ise TLS handshake hatası verdi.
  Arayüz private API/same-origin proxy ile bundan bağımsızlaştırıldı. API doğrudan
  dışarı açılacaksa sertifikanın kapsadığı tek-seviyeli hostname tanımlanmalı.
