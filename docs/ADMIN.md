# Yönetim Erişimi ve Parolalar

trade-ai'de ayrı bir kullanıcı sistemi veya giriş sayfası **yoktur**. Herkese açık
ekranlar (piyasalar, sinyaller, haberler, KAP, portföy…) kimlik doğrulama
istemez. Sistemi değiştirebilen kısımlar iki ayrı katmanla korunur:

| Katman | Neyi korur | Nasıl çalışır | Ayar |
|---|---|---|---|
| **Web yönetim girişi** | `/sistem` ve `/backtest` sayfaları ile bu sayfalardaki tüm form gönderimleri | Tarayıcının kendi kullanıcı adı/parola penceresi (HTTP Basic Auth) | `WEB_ADMIN_USERNAME`, `WEB_ADMIN_PASSWORD` |
| **Backend yönetim anahtarı** | API'nin veri değiştiren tüm uçları | `X-Admin-Token` HTTP başlığı | `ADMIN_API_TOKEN` |

Web sunucusu, yönetim ekranındaki bir işlemi backend'e iletirken
`ADMIN_API_TOKEN` değerini sunucu tarafında ekler. Anahtar tarayıcıya hiçbir
zaman gönderilmez; yöneticinin bilmesi gereken tek şey web giriş parolasıdır.

## Hızlı kurulum

```bash
make init
```

Bu komut `.env.example` dosyasından bir `.env` üretir ve şu değerleri rastgele,
güçlü değerlerle doldurur:

- `POSTGRES_PASSWORD` (ve onunla eşleşen `DATABASE_URL`)
- `ADMIN_API_TOKEN` (64 karakter)
- `WEB_ADMIN_PASSWORD` (32 karakter)

Komut, yönetim girişi için kullanıcı adını ve parolayı ekrana bir kez yazar.
Sonradan bakmak için `.env` dosyasındaki `WEB_ADMIN_USERNAME` /
`WEB_ADMIN_PASSWORD` satırlarına bakabilirsiniz. Mevcut bir `.env` dosyasının
üzerine yazmaz; bilerek yeniden üretmek için `FORCE=1 make init` kullanın.

> **Dikkat:** PostgreSQL parolası, veritabanı volume'u **ilk oluşturulurken**
> kaydedilir. Volume oluştuktan sonra `POSTGRES_PASSWORD` değerini değiştirmek
> veritabanındaki parolayı değiştirmez ve API bağlanamaz. Ayrıntı için aşağıdaki
> [Parola değiştirme](#parola-değiştirme) bölümüne bakın.

## Elle kurulum

`.env.example` dosyasını `.env` olarak kopyalayın ve değerleri kendiniz üretin:

```bash
openssl rand -hex 32       # ADMIN_API_TOKEN için (en az 32 karakter)
openssl rand -hex 16       # WEB_ADMIN_PASSWORD için (en az 16 karakter)
openssl rand -hex 24       # POSTGRES_PASSWORD için
```

```dotenv
ADMIN_API_TOKEN=<64 karakterlik değer>
WEB_ADMIN_USERNAME=admin
WEB_ADMIN_PASSWORD=<32 karakterlik değer>
```

Parolalarda harf ve rakam kullanın. Docker Compose, `.env` içindeki `$`
karakterini değişken olarak yorumlar. `:` karakteri kullanıcı adında
kullanılamaz. `@`, `/` ve `#` ise `DATABASE_URL` içinde kaçış gerektirir.
`openssl rand -hex` çıktısı bu sorunların hiçbirini yaratmaz.

## Giriş ve çıkış

1. Tarayıcıda `https://<alan-adınız>/sistem` adresini açın.
2. Tarayıcı bir giriş penceresi gösterir. `WEB_ADMIN_USERNAME` (varsayılan
   `admin`) ve `WEB_ADMIN_PASSWORD` değerlerini girin.
3. Tarayıcı bilgileri oturum boyunca hatırlar; `/backtest` için tekrar sormaz.

HTTP Basic Auth'ta "çıkış yap" düğmesi yoktur. Çıkmak için tarayıcıyı tamamen
kapatın veya yönetim işlerini gizli pencerede yapın. Parolayı değiştirdiğinizde
eski parolayla açılmış tüm oturumlar bir sonraki istekte reddedilir.

Basic Auth, parolayı her istekte yalnızca base64 kodlamasıyla gönderir;
**şifreleme yapmaz**. İnternete açık her kurulumda HTTPS zorunludur. Coolify ve
`ops/Caddyfile` örneği TLS sertifikasını otomatik alır. `http://localhost`
yalnızca yerel geliştirmede kabul edilebilir.

## Hangi durumda ne olur?

### Web (`/sistem`, `/backtest`)

Docker imajındaki web servisi her zaman production modunda çalışır
(`NODE_ENV=production`). Bu nedenle `ENVIRONMENT=development` olsa bile yönetim
girişi devrededir.

| `WEB_ADMIN_PASSWORD` | `ADMIN_API_TOKEN` | Docker / production | `npm run dev` |
|---|---|---|---|
| dolu | herhangi | Kullanıcı adı + `WEB_ADMIN_PASSWORD` sorulur | Aynı şekilde sorulur |
| boş | dolu | Parola olarak `ADMIN_API_TOKEN` kullanılır (geriye uyumluluk) | Giriş istenmez |
| boş | boş | **HTTP 503** — "Yönetici erişimi yapılandırılmamış" | Giriş istenmez |

Önerilen yapılandırma ilk satırdır: ayrı ve güçlü bir `WEB_ADMIN_PASSWORD`.

### Backend (API yazma uçları)

| `ADMIN_API_TOKEN` | `ENVIRONMENT=production` | `ENVIRONMENT=development` |
|---|---|---|
| dolu | `X-Admin-Token` başlığı zorunlu | `X-Admin-Token` başlığı zorunlu |
| boş | **HTTP 503**, yazma uçları kapalı | **Korumasız** (yalnız yerel kullanım için) |

Korunan uçlar:

| Uç | İşlev |
|---|---|
| `PATCH /api/schedules/{name}` | Tarama takvimini duraklatma, aralık değiştirme |
| `POST /api/schedules/{name}/run` | Bir toplayıcıyı hemen çalıştırma |
| `PUT /api/settings/{key}` | Çalışma zamanı ayarını değiştirme (Gemini anahtarı, bildirimler, risk kuralları…) |
| `DELETE /api/settings/{key}` | Ayarı `.env` varsayılanına döndürme |
| `POST /api/settings/gemini/test` | Ücretli küçük bir Gemini test isteği |
| `POST /api/settings/alerts/test` | Test bildirimi gönderme |
| `POST /api/backtests` | Backtest başlatma |
| `POST /api/system/storage/vacuum` | Veritabanı bakım işlemi |

Okuma (`GET`) uçları anahtar istemez. `GET /api/settings`, gizli değerleri
yalnızca maskeli önizlemeyle (`••••abcd`) döndürür. Varsayılan Coolify
kurulumunda API internete açılmaz; web ona Docker'ın iç ağından ulaşır. API'yi
dışarıya açmanız gerekmiyorsa açmayın.

API'yi doğrudan çağırmak için:

```bash
curl -X POST https://api.example.com/api/schedules/news/run \
  -H "X-Admin-Token: $ADMIN_API_TOKEN"
```

## Coolify / production

Coolify'da değerleri **Environment Variables** ekranına girin ve gizli olanları
"secret" olarak işaretleyin:

```dotenv
ENVIRONMENT=production
ADMIN_API_TOKEN=<openssl rand -hex 32>
WEB_ADMIN_USERNAME=<isterseniz admin dışında bir ad>
WEB_ADMIN_PASSWORD=<openssl rand -hex 16>
```

`docker-compose.yml`, aynı `ADMIN_API_TOKEN` değerini hem `api` hem `web`
servisine verir; iki yere ayrı ayrı girmeniz gerekmez. Değerleri girdikten sonra
`make preflight` ile kontrol edin. Komut, kısa veya örnek parolaları secret
değerlerini ekrana basmadan reddeder. Tam kontrol listesi:
[ops/COOLIFY.md](../ops/COOLIFY.md).

Ek güvenlik katmanı olarak yönetim yollarını reverse proxy üzerinde IP izin
listesiyle veya Cloudflare Access gibi bir kimlik sağlayıcıyla da
sınırlayabilirsiniz.

## Parola değiştirme

Değişiklik ortam değişkenleriyle yapılır. Container'lar yeniden
**oluşturulmalıdır**: `docker compose restart`, `.env` dosyasını yeniden okumaz.

**Web yönetim parolası:**

```bash
# .env içinde WEB_ADMIN_PASSWORD değerini değiştirin, sonra:
docker compose up -d web
```

**Yönetim anahtarı** (api ve web aynı değeri kullandığı için ikisi birlikte):

```bash
# .env içinde ADMIN_API_TOKEN değerini değiştirin, sonra:
docker compose up -d api web
```

Coolify'da değeri değiştirip **Redeploy** yapmanız yeterlidir.

**PostgreSQL parolası:** Önce veritabanındaki parolayı değiştirin, sonra `.env`
dosyasını güncelleyin:

```bash
docker compose exec postgres psql -U tradeai -d tradeai \
  -c "ALTER USER tradeai WITH PASSWORD '<yeni-parola>';"
# .env: POSTGRES_PASSWORD ve DATABASE_URL içindeki parolayı güncelleyin
docker compose up -d api worker
```

## Sorun giderme

| Belirti | Neden / çözüm |
|---|---|
| `/sistem` açılınca **503 "Yönetici erişimi yapılandırılmamış"** | Web container'ında `WEB_ADMIN_PASSWORD` ve `ADMIN_API_TOKEN` boş. Birini (tercihen ikisini) ayarlayıp `docker compose up -d web` çalıştırın. |
| Giriş penceresi sürekli tekrar açılıyor | Kullanıcı adı veya parola yanlış. Değeri `.env` dosyasından kopyalayın; başında veya sonunda boşluk kalmadığından emin olun. Değeri değiştirdikten sonra container'ı yeniden oluşturdunuz mu? |
| Sayfa açılıyor ama işlemler **"Gecersiz yonetim anahtari"** hatası veriyor | `api` ve `web` farklı `ADMIN_API_TOKEN` değerleriyle çalışıyor. İkisini birlikte yeniden oluşturun: `docker compose up -d api web`. |
| İşlemler **"ADMIN_API_TOKEN production ortaminda zorunludur"** hatası veriyor | `ENVIRONMENT=production` iken `ADMIN_API_TOKEN` boş. Bir değer üretip ayarlayın. |
| Parolayı unuttum | Parola `.env` dosyasında (Coolify'da Environment Variables ekranında) düz metin olarak durur. Bulamazsanız yeni bir değer yazıp container'ı yeniden oluşturun. |
| Yerelde `npm run dev` ile giriş hiç sorulmuyor | Beklenen davranış: geliştirme modunda `WEB_ADMIN_PASSWORD` boşsa giriş kapalıdır. Test etmek için `web/.env.local` içine `WEB_ADMIN_PASSWORD=...` yazın. |
