# Codex Çalışma / Devir Notları

Son güncelleme: 2026-09-07 (Europe/Istanbul)

Bu dosya, Codex'in yaptığı değişiklikleri Claude ve diğer ajanların hızlıca
inceleyebilmesi için tutulur. Kanonik faz durumu `PROGRESS.md`, değişmemesi
gereken ürün kararları `CLAUDE.md` içindedir.

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

### Sıradaki iş

Faz 4 — LLM değerlendirme katmanı. Haber/KAP girdilerinin ortak değerlendirme
şeması, model çağrı bütçesi ve deterministik yeniden-işleme anahtarı şemadan
önce netleştirilmeli.

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
