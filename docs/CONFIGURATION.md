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
| `TZ` | `Europe/Istanbul` | Zamanlanmış işlerin ve tarihlerin saat dilimi. |
| `CORS_ORIGINS` | `http://localhost:3000` | API'ye tarayıcıdan erişebilecek originler, virgülle ayrılır. Production'da gerçek HTTPS domaini yazın. |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,api` | API'nin kabul ettiği `Host` başlıkları. Docker'daki iç ad `api` her zaman listede kalmalıdır. |

### Veritabanı ve kuyruk

| Değişken | Açıklama |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | PostgreSQL container'ının ilk kurulum bilgileri. |
| `DATABASE_URL` | `postgresql+asyncpg://KULLANICI:PAROLA@postgres:5432/DB`. Parola `POSTGRES_PASSWORD` ile aynı olmalıdır. |
| `REDIS_URL` | Compose içinde `redis://redis:6379/0` olarak sabitlenir. |

### Yönetim erişimi

| Değişken | Açıklama |
|---|---|
| `ADMIN_API_TOKEN` | Backend yazma uçlarının anahtarı (en az 32 karakter). |
| `WEB_ADMIN_USERNAME` | `/giris` sayfasındaki yönetici kullanıcı adı (varsayılan `admin`). |
| `WEB_ADMIN_PASSWORD` | `/giris` sayfasındaki yönetici parolası (en az 16 karakter). Değiştirmek açık oturumları kapatır. |

Davranış tabloları ve parola değiştirme adımları: [ADMIN.md](ADMIN.md).

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
  pozisyon ve sektör ağırlığı, yeniden dengeleme.
- **Bildirimler:** açık/kapalı, Telegram bot token ve chat ID, webhook URL,
  izlenen hisseler, yüksek skor eşiği.
- **Sistem uyarıları:** N8N webhook URL.

Gizli değerler ekranda yalnızca son dört karakteriyle gösterilir.

## Tarama takvimi

Veri toplama ve analiz işleri `/sistem` ekranındaki takvim bölümünden
duraklatılabilir, aralıkları değiştirilebilir veya elle çalıştırılabilir. Ayarlar
PostgreSQL'de kalıcıdır.

| İş | Varsayılan aralık |
|---|---|
| KAP bildirimleri, haber akışı | 5 dakika |
| AI değerlendirmeleri, bileşik sinyaller | 10 dakika |
| Hisse evreni, temel analiz, analist görüşleri, EOD fiyatlar, paper portföy, TEFAS fon akımı ve diğer günlük işler | Günde bir (belirli saatte) |
