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
- [ ] `docker compose up -d --build` ile uçtan uca yerel doğrulama (Docker
      Desktop bu oturumda başlatıldı, daemon açılışı bekleniyor)
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
🔶 Kod tarafı tamamlandı — Docker/Postgres bloke olduğu için gerçek DB
   entegrasyon testi bekliyor (bkz. Faz 0 "Docker Desktop bloke" notu)

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
      **5 testle DB'siz doğrulandı** (`tests/test_instrument_mapping.py`)
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
- [ ] `docker compose exec worker python -m scripts.run_once instruments`
      (gerçek Postgres'e karşı, x2 idempotency testi) — **Docker'ı bekliyor**
- [ ] `docker compose exec worker python -m scripts.run_once prices --tickers THYAO,ASELS,GARAN --days 30`
      (küçük örnekle önce dene, sonra tam backfill) — **Docker'ı bekliyor**

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
⬜ Başlanmadı

## Faz 3 — Haber Toplayıcı
⬜ Başlanmadı

## Faz 4 — LLM Değerlendirme Katmanı
⬜ Başlanmadı

## Faz 5 — Temel Analiz Motoru
⬜ Başlanmadı

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

- `isyatirimhisse` kütüphanesinin güncel fonksiyon imzası doğrulanmadı —
  `smoke_sources.py` iki farklı import yolunu deniyor (`fetch_stock_data` /
  `StockData`), gerçek çalıştırmada hangisinin tuttuğu görülecek.
- TEFAS smoke kontrolü `BindHistoryInfo` endpoint'ini deniyor — bu endpoint
  daha önce doğrulanan `dagilimSiraliGetirT`'ten farklı, ikisi de teyit
  edilmeli.
- RSS feed URL'leri (`bloomberght.com/rss`, `tr.investing.com/rss/news.rss`)
  tahmini — gerçek çalıştırmada 404 verirse doğru feed URL'i bulunacak.
