# Yapılandırma

trade-ai iki katmanlı yapılandırma kullanır:

1. **Ortam değişkenleri** (`.env` veya Coolify Environment Variables): altyapı,
   parolalar ve varsayılan değerler. Örnek dosya: [`.env.example`](../.env.example).
2. **Çalışma zamanı ayarları** (`/sistem` → Ayarlar): bazı değerler container
   yeniden başlatılmadan değiştirilebilir. Bunlar Redis'te saklanır ve ilgili
   ortam değişkeninin önüne geçer. Ayar silinirse (veya Redis boşalırsa) sistem
   `.env` varsayılanına döner.

`make init`, `.env` dosyasını parolalar rastgele doldurulmuş olarak üretir
(bkz. [ADMIN.md](ADMIN.md)).

## Ortam değişkenleri

### Genel

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` olduğunda güvenlik kontrolleri sıkılaşır (ör. `ADMIN_API_TOKEN` zorunlu olur). |
| `LOG_LEVEL` | `INFO` | Backend log seviyesi. |
| `SOURCE_COMMIT` | boş | Elle ayarlanmaz. İmajın derlendiği commit; `docker-compose.yml` build argümanı olarak geçirir (Coolify'da "Include Source Commit in Build", yerelde `make dev`). Sol menüde ve `/health` yanıtında sürümün yanında görünür. |
| `TZ` | `Europe/Istanbul` | Zamanlanmış işlerin ve tarihlerin saat dilimi. |
| `CORS_ORIGINS` | `http://localhost:3000` | API'ye tarayıcıdan erişebilecek originler, virgülle ayrılır. Production'da gerçek HTTPS domaini yazın. |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,api` | API'nin kabul ettiği `Host` başlıkları. Docker'daki iç ad `api` her zaman listede kalmalıdır. |

### Veritabanı ve kuyruk

| Değişken | Açıklama |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | PostgreSQL container'ının ilk kurulum bilgileri. |
| `DATABASE_URL` | `postgresql+asyncpg://KULLANICI:PAROLA@postgres:5432/DB`. Parola `POSTGRES_PASSWORD` ile aynı olmalıdır. |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | Süreç başına SQLAlchemy bağlantı havuzu (varsayılan 5 + 10). Her API süreci ve worker ayrı havuz açar; `(API_WORKERS + 1) × (DB_POOL_SIZE + DB_MAX_OVERFLOW)` Postgres `max_connections` değerinin (varsayılan 100) altında kalmalıdır. |
| `REDIS_URL` | Compose içinde `redis://redis:6379/0` olarak sabitlenir. |

### Yönetim erişimi

| Değişken | Açıklama |
|---|---|
| `ADMIN_API_TOKEN` | Backend yazma uçlarının anahtarı (en az 32 karakter). |
| `WEB_ADMIN_USERNAME` | `/giris` sayfasındaki yönetici kullanıcı adı (varsayılan `admin`). |
| `WEB_ADMIN_PASSWORD` | `/giris` sayfasında kullanıcı adıyla girilen yerleşik yöneticinin parolası (en az 16 karakter). Değiştirmek açık oturumları kapatır. |

### Kullanıcı hesapları

Ayrıntılar ve kurulum adımları: [ADMIN.md → Kullanıcı hesapları](ADMIN.md#kullanıcı-hesapları).

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `REGISTRATION_MODE` | `invite` | `invite`: yalnız davet koduyla kayıt (kapalı beta). `open`: herkes kayıt olabilir. `closed`: yeni kayıt yok. `/sistem` → Ayarlar'dan container yeniden başlatılmadan değişir. |
| `SESSION_TTL_DAYS` | `30` | Kullanıcı oturumunun ömrü (gün). |
| `PAPER_MAX_PORTFOLIOS_PER_USER` | `5` | Bir kullanıcının açabileceği en fazla paper portföy (strateji + manuel). |
| `PAPER_MAX_PENDING_ORDERS` | `20` | Manuel portföy başına aynı anda bekleyebilecek en fazla emir. |
| `BACKTEST_DAILY_LIMIT_PER_USER` | `10` | Kullanıcı başına günlük backtest koşusu (İstanbul saatiyle gün). Yönetici rolü muaftır. |
| `BACKTEST_MAX_ACTIVE_PER_USER` | `1` | Kullanıcı başına aynı anda sırada bekleyen ya da çalışan koşu. Worker zaten koşuları tek tek hesaplar. |
| `PUBLIC_BASE_URL` | `http://localhost:3000` | E-postalardaki doğrulama ve parola sıfırlama bağlantılarının kökü. Production'da sitenin `https://` adresi olmalıdır; bağlantı adresi gelen isteğin `Host` başlığından türetilmez (sahte bağlantı saldırısına karşı). |
| `SMTP_HOST`, `SMTP_PORT` | boş, `587` | E-posta sunucusu. `SMTP_HOST` veya `MAIL_FROM` boşsa e-posta gönderilmez: geliştirmede bağlantı worker log'una yazılır, production'da yalnız uyarı loglanır ve kullanıcıların `/sistem`'den elle doğrulanması gerekir. |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | boş | SMTP kimlik bilgileri (sağlayıcının verdiği kullanıcı / API anahtarı). |
| `SMTP_SECURITY` | `starttls` | `starttls` (587), `ssl` (465) veya `none` (yalnız yerel test sunucusu). |
| `MAIL_FROM` | boş | Gönderen adresi, ör. `TradeAI <no-reply@example.com>`. Alan adında SPF/DKIM kayıtları olmayan adresten giden e-postalar çoğunlukla gereksiz klasörüne düşer. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | boş | Google ile giriş için OAuth istemcisi (Google Cloud Console → Kimlik bilgileri → OAuth istemci kimliği, tür: Web uygulaması). Yetkili yönlendirme adresi `<PUBLIC_BASE_URL>/giris/google/callback` olmalıdır. İkisi de doluysa giriş ve kayıt sayfalarında Google düğmesi görünür; yalnız API servisine verilir. |
| `USER_ALERTS_ENABLED` | `true` | Kullanıcıların kendi bildirimleri: Telegram bağlama, izleme listesi/portföy hisselerinde anlık etiket değişimi ve günlük özet. `/sistem` → Ayarlar'dan da kapatılabilir. Ayrıntı: [ADMIN.md → Kişisel bildirimler](ADMIN.md#kişisel-bildirimler). |
| `CONTACT_EMAIL` | boş | `/gizlilik` sayfasında KVKK talepleri için gösterilen iletişim adresi (web servisine verilir). Boşsa kullanıcıya kayıtlı adresinden yazması söylenir. |

Davranış tabloları ve parola değiştirme adımları: [ADMIN.md](ADMIN.md).

### TCMB EVDS (makro göstergeler)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `EVDS_API_KEY` | — | TCMB EVDS API anahtarı (ücretsiz; evds2.tcmb.gov.tr üyelik → profil). Tanımlı değilse `/makro` sayfasındaki kur ve TÜFE kartları görünmez. |

Anahtar tanımlandıktan sonra ilk veriyi almak için
`docker compose exec api python -m scripts.run_once evds`.

### Gemini (yapay zeka değerlendirmesi)

LLM değerlendirmesi ücretli API çağrısı yapar ve **varsayılan olarak kapalıdır**.
Anahtar tanımlı olsa bile `LLM_ENABLED=true` olmadan hiçbir çağrı yapılmaz.

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `GEMINI_API_KEY` | — | Google AI Studio API anahtarı. |
| `LLM_ENABLED` | `false` | Toplu değerlendirmeyi açar. |
| `GEMINI_API_MODE` | `interactions` | `interactions` veya `generate_content`. |
| `GEMINI_MODEL_TIER1` | `gemini-3.8-flash` | Tüm kaynakların ilk, ucuz sınıflandırması. |
| `GEMINI_MODEL_TIER2` | `gemini-3.1-pro-preview` | Yüksek etkili kaynakların ikinci, derin incelemesi. |
| `LLM_TIER2_MIN_IMPACT` | `70` | Tier 2'ye gönderilecek en düşük etki skoru. |
| `LLM_BATCH_SIZE` | `20` | Bir çalışmada değerlendirilecek en fazla kaynak sayısı. |
| `LLM_TIER1_GROUP_SIZE` | `5` | Tek Tier 1 isteğinde gruplanan kaynak sayısı. |
| `LLM_MAX_ATTEMPTS` | `3` | Hatalı kaynak için en fazla deneme sayısı. |
| `LLM_DAILY_INPUT_TOKEN_LIMIT` | `500000` | Günlük girdi token bütçesi (`0` = sınırsız). |
| `LLM_DAILY_OUTPUT_TOKEN_LIMIT` | `100000` | Günlük çıktı token bütçesi (`0` = sınırsız). |
| `LLM_MAX_SOURCE_CHARS` | `12000` | Modele gönderilecek kaynak metninin üst sınırı. |

Model adları ve fiyatlar sık değişir. Açmadan önce
[ai.google.dev/pricing](https://ai.google.dev/pricing) sayfasını kontrol edin.
Bağlantıyı, toplu değerlendirmeyi açmadan önce `/sistem` ekranındaki
"Bağlantı kontrolleri" bölümünden tek küçük istekle doğrulayabilirsiniz.

### Bildirimler

| Değişken | Açıklama |
|---|---|
| `N8N_WEBHOOK_URL` | Sistem sağlık uyarılarının gönderileceği webhook (opsiyonel). |
| `MONITORING_ALERT_COOLDOWN_SECONDS` | Aynı sorun için tekrar uyarı göndermeden önce beklenecek süre. |

Telegram ve sinyal bildirimleri (`alerts_*`) yalnızca `/sistem` ekranından
ayarlanır.

### Kaynak limitleri ve portlar

| Değişken | Açıklama |
|---|---|
| `API_PORT`, `WEB_PORT` | Yerel geliştirmede host'a açılan portlar (`docker-compose.override.yml`). Coolify bu dosyayı kullanmaz. |
| `POSTGRES_MEMORY_LIMIT`, `REDIS_MEMORY_LIMIT`, `API_MEMORY_LIMIT`, `WORKER_MEMORY_LIMIT`, `WEB_MEMORY_LIMIT` | Container bellek sınırları. |
| `API_WORKERS` | API container'ındaki uvicorn süreç sayısı (varsayılan 2). Migration'lar süreçler açılmadan önce bir kez çalışır. Süreç başına ~150-300 MB bellek: 3 ve üstü için `API_MEMORY_LIMIT`'i artırın ve DB havuzu toplamını kontrol edin. Sunucunun CPU çekirdek sayısını aşmayın. |
| `WORKER_CPUS` | Worker container'ının CPU tavanı (çekirdek, varsayılan 1; `0.5` gibi kesirli değer olabilir). Worker ayrıca `nice -n 10` ile düşük öncelikte çalışır: CPU boştayken tam hız kullanır, web ve API CPU istediğinde sıra onlara geçer. Tavan, saat başı toplu işler başladığında sayfaların yavaşlamasını önlemek içindir. |
| `WORKER_MAX_JOBS` | Worker'da aynı anda çalışan iş sayısı (varsayılan 3, ARQ'nun kendi varsayılanı 10). Fazlası Redis kuyruğunda sıra bekler, kaybolmaz. Worker canlılık sinyali iş slotlarından bağımsız yazıldığı için düşük değer `/sistem`'de worker'ı bayat göstermez. |
| `WEB_WORKERS` | Web container'ındaki Next.js süreç sayısı (varsayılan 2; `auto` = container'ın görebildiği CPU sayısı, en fazla 16). Next sayfaları tek iş parçacığında render ettiği için tek süreç tek çekirdeğe sınırlıdır; süreçler aynı portu Node cluster ile paylaşır. Süreç başına ~150-250 MB: `WEB_MEMORY_LIMIT` (varsayılan 1G) süreç sayısıyla birlikte artırılmalıdır, her sürecin V8 heap'i bu sınırın %75'inin süreç sayısına bölümüyle sınırlanır. Süreç belleğindeki durumlar süreç başınadır: kısa süreli API yanıt önbelleği her süreçte ayrı dolar (API'ye giden istek en fazla süreç sayısı kadar artar) ve `/giris` kaba kuvvet sınırları süreç sayısına bölünerek toplamda aynı kalır. `1` eski tek süreçli davranıştır. `/health` yanıtındaki `workers` alanı çalışan değeri gösterir. |

### Veri toplayıcılar

| Değişken | Açıklama |
|---|---|
| `COLLECTOR_USER_AGENT` | Dış kaynaklara gönderilen `User-Agent`. Kendi kurulumunuzu tanıtan bir değer (ör. iletişim adresi) yazmanız önerilir. |
| `KAP_RATE_LIMIT_PER_SEC` | KAP'a saniyedeki en fazla istek sayısı. Kaynağa saygı için düşük tutun. |

## Çalışma zamanı ayarları (`/sistem`)

Aşağıdaki ayarlar yönetim girişinden sonra `/sistem` ekranından değiştirilebilir:

- **Gemini:** API anahtarı, API modu, Tier 1/Tier 2 modelleri, grup ve batch
  boyutu, günlük çıktı token bütçesi, LLM'in açık/kapalı durumu.
- **Paper portföy riskleri:** stop-loss, take-profit, takip eden stop, en fazla
  pozisyon ve sektör ağırlığı, yeniden dengeleme. Varsayılanlar: zarar-kes
  %15, kâr-al ve takip eden stop kapalı, tek pozisyon %10, sektör %30,
  yeniden dengeleme açık. Ekrandan kaydedilen değer varsayılanın önüne geçer.
- **Bildirimler:** açık/kapalı, Telegram bot token ve chat ID, webhook URL,
  izlenen hisseler, yüksek skor eşiği, günlük özet. Günlük özet açıksa her
  işlem günü 19:15'te (takvimden değiştirilebilir) BIST100, paper portföy,
  günün işlemleri ve skor hareketleri tek mesajla gönderilir; aynı gün için
  ikinci kez gönderilmez.
- **Kullanıcı bildirimleri:** açık/kapalı. Kullanıcılar Telegram'ı Hesabım →
  Bildirimler'den kendileri bağlar; yukarıdaki bot token'i kullanılır.
- **Sistem uyarıları:** N8N webhook URL.
- **Kullanıcı kaydı:** davet koduyla / herkese açık / kapalı. Davet kodları,
  kullanıcı listesi, elle e-posta doğrulama, devre dışı bırakma ve yönetici
  rolü aynı ekrandaki "Kullanıcılar ve davetler" bölümündedir.

Gizli değerler ekranda yalnızca son dört karakteriyle gösterilir.

## Tarama takvimi

Veri toplama ve analiz işleri `/sistem` ekranındaki takvim bölümünden
duraklatılabilir, aralıkları değiştirilebilir veya elle çalıştırılabilir. Ayarlar
PostgreSQL'de kalıcıdır.

| İş | Varsayılan aralık |
|---|---|
| KAP bildirimleri, haber akışı | 5 dakika |
| AI değerlendirmeleri, bileşik sinyaller | 10 dakika |
| Hisse evreni, temel analiz, analist görüşleri, EOD fiyatlar, paper portföy, TEFAS fon akımı, günlük özet bildirimi, kullanıcı günlük özetleri (19:20) ve diğer günlük işler | Günde bir (belirli saatte) |
