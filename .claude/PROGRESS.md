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
- [ ] `docker compose up -d --build` ile uçtan uca yerel doğrulama (Docker Desktop
      gerekiyor — bu oturumda sadece Python venv ile smoke test çalıştırıldı,
      container build'i henüz denenmedi)
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
⬜ Başlanmadı

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
