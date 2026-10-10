# Yönetim Erişimi ve Parolalar

trade-ai'de tek bir yönetici hesabı vardır; kullanıcı kaydı veya çoklu kullanıcı
yoktur. Herkese açık ekranlar (piyasalar, sinyaller, haberler, KAP, portföy…)
giriş istemez. Sistemi değiştirebilen kısımlar iki katmanla korunur:

| Katman | Neyi korur | Nasıl çalışır | Ayar |
|---|---|---|---|
| **Web yönetim girişi** | `/sistem` ve `/backtest` sayfaları ile bu sayfalardaki tüm form gönderimleri | `/giris` sayfası; başarılı girişte 12 saatlik imzalı oturum çerezi | `WEB_ADMIN_USERNAME`, `WEB_ADMIN_PASSWORD` |
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

1. Menüden **Sistem Sağlığı** veya **Backtest** ekranını açın (ya da doğrudan
   `https://<alan-adınız>/giris` adresine gidin).
2. Oturum yoksa **Yönetici girişi** sayfasına yönlendirilirsiniz.
   `WEB_ADMIN_USERNAME` (varsayılan `admin`) ve `WEB_ADMIN_PASSWORD`
   değerlerini girin.
3. Giriş sonrası açmak istediğiniz sayfaya geri dönersiniz. Oturum 12 saat
   geçerlidir; süre dolunca giriş sayfası yeniden gelir.
4. Çıkmak için `/sistem` veya `/backtest` başlığındaki **Çıkış yap** düğmesine
   basın.

Oturum ayrıntıları:

- Çerez (`tradeai_admin`) `HttpOnly` ve `SameSite=Lax` olarak verilir. Site HTTPS
  arkasındaysa (`X-Forwarded-Proto: https`; Coolify ve Caddy bunu gönderir)
  `Secure` da eklenir.
- Çerez parolayı değil, yalnızca kullanıcı adını ve bitiş zamanını taşır. İmza
  anahtarı yapılandırılmış paroladan türetilir. **Parolayı veya kullanıcı adını
  değiştirmek tüm açık oturumları anında geçersiz kılar.** Bütün cihazlardan
  çıkış yapmanın yolu budur.
- Kaba kuvvet koruması: aynı istemciden 15 dakikada 5 hatalı deneme o istemciyi
  kilitler. Toplamda 30 hatalı deneme ise girişi 15 dakikalığına herkes için
  kilitler. Kilit web container'ı yeniden başlatılınca sıfırlanır.
- Giriş formu parolayı düz metin olarak gönderir. İnternete açık her kurulumda
  HTTPS zorunludur. Coolify ve `ops/Caddyfile` örneği TLS sertifikasını
  otomatik alır. `http://localhost` yalnızca yerel kullanımda kabul edilebilir.

### İzleme listesi ve bildirimler

Ziyaretçilerin izleme listesi yalnızca kendi tarayıcılarında kalır. Yönetici
girişliyken liste sunucuya senkronlanır (`/api/watchlist`). Telegram ve webhook
bildirimleri şu hisselerin etiket değişimlerini izler: paper portföydeki
pozisyonlar, bu liste ve `/sistem` ekranındaki "izlenen hisseler" ayarı. İlk
girişte o tarayıcıdaki liste sunucudakiyle birleştirilir. Sonraki açılışlarda
sunucudaki liste esas alınır.

## Hangi durumda ne olur?

### Web (`/sistem`, `/backtest`)

Docker imajındaki web servisi her zaman production modunda çalışır
(`NODE_ENV=production`). Bu nedenle `ENVIRONMENT=development` olsa bile yönetim
girişi devrededir.

| `WEB_ADMIN_PASSWORD` | `ADMIN_API_TOKEN` | Docker / production | `npm run dev` |
|---|---|---|---|
| dolu | herhangi | `/giris` sayfası: kullanıcı adı + `WEB_ADMIN_PASSWORD` | Aynı şekilde |
| boş | dolu | Parola olarak `ADMIN_API_TOKEN` kullanılır (geriye uyumluluk) | Giriş istenmez |
| boş | boş | Yönetim sayfaları **HTTP 503**; `/giris` yapılandırma uyarısı gösterir | Giriş istenmez |

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

Ek güvenlik katmanı olarak `/giris`, `/sistem` ve `/backtest` yollarını reverse
proxy üzerinde IP izin listesiyle veya Cloudflare Access gibi bir kimlik
sağlayıcıyla da sınırlayabilirsiniz.

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
| `/sistem` açılınca **503 "Yönetici erişimi yapılandırılmamış"** veya `/giris` aynı uyarıyı gösteriyor | Web container'ında `WEB_ADMIN_PASSWORD` ve `ADMIN_API_TOKEN` boş. Birini (tercihen ikisini) ayarlayıp `docker compose up -d web` çalıştırın. |
| "Kullanıcı adı veya parola hatalı" | Kullanıcı adı veya parola yanlış. Değeri `.env` dosyasından kopyalayın; başında veya sonunda boşluk kalmadığından emin olun. Değeri değiştirdikten sonra container'ı yeniden oluşturdunuz mu? |
| "Çok fazla hatalı deneme" | Kaba kuvvet kilidi devrede. 15 dakika bekleyin veya web container'ını yeniden başlatın: `docker compose restart web`. |
| Giriş yaptıktan hemen sonra tekrar giriş sayfası geliyor | Çerez kaydedilmiyor. Site HTTP üzerinden açılıyor ama proxy `X-Forwarded-Proto: https` gönderiyorsa tarayıcı `Secure` çerezi saklamaz; siteyi `https://` ile açın. Tarayıcıda çerezlerin engellenmediğini de kontrol edin. |
| Sayfa açılıyor ama işlemler **"Gecersiz yonetim anahtari"** hatası veriyor | `api` ve `web` farklı `ADMIN_API_TOKEN` değerleriyle çalışıyor. İkisini birlikte yeniden oluşturun: `docker compose up -d api web`. |
| İşlemler **"ADMIN_API_TOKEN production ortaminda zorunludur"** hatası veriyor | `ENVIRONMENT=production` iken `ADMIN_API_TOKEN` boş. Bir değer üretip ayarlayın. |
| Parolayı unuttum | Parola `.env` dosyasında (Coolify'da Environment Variables ekranında) düz metin olarak durur. Bulamazsanız yeni bir değer yazıp container'ı yeniden oluşturun. |
| Yerelde `npm run dev` ile giriş sayfası hiç gelmiyor | Beklenen davranış: geliştirme modunda `WEB_ADMIN_PASSWORD` boşsa giriş kapalıdır. Test etmek için `web/.env.local` içine `WEB_ADMIN_PASSWORD=...` yazın. |
