# Codex Çalışma / Devir Notları

Son güncelleme: 2026-09-07 (Europe/Istanbul)

Bu dosya, Codex'in yaptığı değişiklikleri Claude ve diğer ajanların hızlıca
inceleyebilmesi için tutulur. Kanonik faz durumu `PROGRESS.md`, değişmemesi
gereken ürün kararları `CLAUDE.md` içindedir.

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
