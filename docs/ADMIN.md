# Yönetim Erişimi ve Parolalar

Herkese açık ekranlar (piyasalar, sinyaller, haberler, KAP, model portföy…)
giriş istemez. Ziyaretçiler isterse hesap açar; hesapla izleme listesi hesapta
saklanır, kişisel paper portföyler (`/portfoylerim`) kurulur ve kişisel backtest
koşulur (`/backtest`) (bkz. [Kullanıcı hesapları](#kullanıcı-hesapları)).

Yönetici iki yoldan olunur:

- **Yerleşik yönetici:** `.env`'deki `WEB_ADMIN_USERNAME` / `WEB_ADMIN_PASSWORD`.
  `/giris` formuna e-posta yerine kullanıcı adı yazılır.
- **Yönetici hesabı:** rolü `admin` olan kullanıcı hesabı
  (`make create-admin EMAIL=...` ya da `/sistem` → Kullanıcılar).

Sistemi değiştirebilen kısımlar iki katmanla korunur:

| Katman | Neyi korur | Nasıl çalışır | Ayar |
|---|---|---|---|
| **Web yönetim girişi** | `/sistem` sayfası ile oradaki tüm form gönderimleri (`/backtest` her hesaba açıktır; yerleşik yönetici orada sistem koşularını görür) | `/giris` sayfası. Yerleşik yönetici 12 saatlik imzalı çerez alır; yönetici hesabı normal kullanıcı oturumuyla girer, rolü her istekte API'den doğrulanır | `WEB_ADMIN_USERNAME`, `WEB_ADMIN_PASSWORD`, kullanıcı rolü |
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
2. Oturum yoksa **Giriş yap** sayfasına yönlendirilirsiniz.
   - Yerleşik yönetici: "E-posta" alanına `WEB_ADMIN_USERNAME` değerini
     (varsayılan `admin`; `@` içermez), parola alanına `WEB_ADMIN_PASSWORD`
     değerini girin.
   - Yönetici hesabı: e-posta adresinizi ve hesap parolanızı girin.
3. Giriş sonrası açmak istediğiniz sayfaya geri dönersiniz. Yerleşik yönetici
   oturumu 12 saat, hesap oturumu 30 gün geçerlidir.
4. Çıkmak için `/sistem` başlığındaki ya da sağ üstteki hesap menüsündeki
   **Çıkış yap** düğmesine basın.
5. Girişli ama yönetici olmayan bir kullanıcı `/sistem` açarsa "Bu sayfa
   yöneticilere açık" sayfası (HTTP 403) görür. `/backtest` her hesaba açıktır.

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

Ziyaretçilerin izleme listesi yalnızca kendi tarayıcılarında kalır. Hesapla
girişli kullanıcının listesi hesabına kaydedilir (`/api/me/watchlist`); bu
listeler bildirimlere dahil değildir. Yerleşik yönetici girişliyken liste
bildirimlerin izlediği ortak listeye senkronlanır (`/api/watchlist`).
Telegram ve webhook bildirimleri şu hisselerin etiket değişimlerini izler:
paper portföydeki pozisyonlar, bu ortak liste ve `/sistem` ekranındaki
"izlenen hisseler" ayarı.

Bir hesapla o tarayıcıdaki ilk girişte, ziyaretçiyken eklenen hisseler hesaptaki
listeyle birleştirilir. Sonraki açılışlarda hesaptaki liste esas alınır.
Çıkışta tarayıcıdaki liste silinir; ortak bir bilgisayarda sonraki kişiye
kalmaz.

## Kullanıcı hesapları

### Nasıl çalışır

- Kayıt: e-posta + parola (en az 10 karakter) + kullanım koşulları onayı.
  Kayıt modu `invite` ise davet kodu da gerekir.
- **E-posta doğrulanmadan giriş yapılamaz.** Doğrulama bağlantısı 48 saat,
  parola sıfırlama bağlantısı 1 saat geçerlidir ve tek kullanımlıktır.
- Parolalar argon2id ile özetlenir. Oturum token'ı yalnız `tradeai_session`
  çerezinde (HttpOnly, SameSite=Lax, HTTPS'te Secure) durur; veritabanında
  yalnız sha256 özeti saklanır. Oturum varsayılan 30 gün geçerlidir
  (`SESSION_TTL_DAYS`).
- Parola değişince diğer cihazlardaki oturumlar, parola sıfırlanınca tüm
  oturumlar kapanır ve kullanıcıya bilgi e-postası gider.
- Kayıt ve parola sıfırlama, e-posta kayıtlı olsun olmasın aynı yanıtı verir;
  zaten kayıtlı adrese "zaten hesabın var" e-postası gider. Böylece formdan
  hangi adreslerin kayıtlı olduğu öğrenilemez.
- Hız sınırları Redis'te tutulur (tüm web süreçleri ortak sayar): aynı IP'den
  15 dakikada 20, aynı e-postaya 8 hatalı giriş; IP başına saatte 5 kayıt;
  adres başına saatte 5 e-posta.
- Kullanıcı `/hesap` sayfasından adını ve parolasını değiştirir, açık
  oturumlarını görüp kapatır ve hesabını kalıcı olarak siler (KVKK).
- `/api/me/*` uçları `Authorization: Bearer <oturum>` ister. `/api/auth/*` ve
  `/api/admin/*` uçlarını yalnız web sunucusu `X-Admin-Token` ile çağırır.

### Production kurulumu

1. **Adresi ayarlayın:** `PUBLIC_BASE_URL=https://<alan-adınız>`. E-postadaki
   bağlantılar buradan üretilir.
2. **SMTP'yi ayarlayın** (Resend, Brevo, Amazon SES ya da kendi sunucunuz):
   `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`,
   `SMTP_SECURITY`, `MAIL_FROM`. Gönderen alan adına sağlayıcının verdiği SPF
   ve DKIM kayıtlarını ekleyin; yoksa e-postalar gereksiz klasörüne düşer.
   SMTP yokken kayıt yine çalışır, ama doğrulama e-postası gitmez. O durumda
   kullanıcıyı `/sistem` → Kullanıcılar → **Doğrula** ile elle etkinleştirin.
3. **Yönetici hesabı açın** (isteğe bağlı; yerleşik yönetici çalışmaya devam
   eder):

   ```bash
   make create-admin EMAIL=yonetici@example.com
   # Coolify'da api container'ının terminalinde:
   python -m scripts.create_admin --email yonetici@example.com
   ```

   Kullanıcı yoksa parola sorulur ve doğrulanmış bir yönetici oluşturulur.
   Kullanıcı zaten varsa yalnız rolü `admin` yapılır.
4. **Kayıt modunu seçin:** varsayılan `invite` (kapalı beta). `/sistem` →
   "Kullanıcılar ve davetler" bölümünde davet kodu üretin (kullanım hakkı ve
   geçerlilik süresiyle) ve kodu kişiye iletin. Herkese açmak için `/sistem`
   → Ayarlar → **Kullanıcı Kaydı** → "Herkese açık".

### Yönetici işlemleri (`/sistem` → Kullanıcılar ve davetler)

| İşlem | Etkisi |
|---|---|
| Davet kodu oluştur / iptal et | `XXXX-XXXX-XXXX` biçiminde kod; kullanım hakkı dolunca, süresi geçince ya da iptal edilince kayıtta reddedilir. |
| Doğrula | E-postayı doğrulanmış sayar (SMTP yokken ya da e-posta ulaşmadığında). |
| Devre dışı bırak / etkinleştir | Devre dışı hesap giriş yapamaz; açık oturumları anında kapanır. |
| Yönetici yap / yöneticiliği al | Rolü `admin` olan hesap `/sistem`'e girer ve backtest kotasından muaftır. |

Süresi dolmuş oturum ve token kayıtları worker tarafından her gece 04:20'de
silinir.

### Kişisel paper portföyler

- Kullanıcı en fazla `PAPER_MAX_PORTFOLIOS_PER_USER` (varsayılan 5) portföy açar.
  İki tür vardır:
  - **Strateji:** bileşik sinyali kullanıcının seçtiği eşiklerle (giriş/çıkış
    skoru, güven, pozisyon sayısı, zarar-kes, sektör tavanı…) otomatik izler.
    Hazır şablonlar: Model stratejisi, Temkinli, Agresif.
  - **Manuel:** kullanıcı sanal alış/satış emri verir (portföy sayfasından ya da
    hisse sayfasındaki "paper emri ver" bağlantısından).
- Tüm portföyler, model portföyle aynı gün sonu işinde (`paper_portfolio`
  takvimi, varsayılan 18:46) işlenir. Günün sinyal ve fiyat verisi bir kez
  yüklenir; her portföy ayrı transaction'da işlenir, biri hata alırsa diğerleri
  etkilenmez ve hata portföyün kartında görünür.
- **Geleceğe bakma yoktur:** yeni portföy ve manuel emir, 18:00'den önce
  verildiyse o günün, sonra verildiyse bir sonraki işlem gününün kapanışından
  işlem görür. Geçmiş günler oynatılmaz.
- Komisyon (%0,1), kayma (%0,05), tavan/tabanda işlem yapılmaması ve düşük
  hacim filtresi herkes için aynıdır. Tavan/tabanda kalan ya da işlem görmeyen
  hissedeki manuel emir bekler; 7 gün içinde gerçekleşmezse reddedilir.
- Herkese açık `/api/paper/*` uçları ve `/portfoy` yalnız model portföyü
  gösterir. Telegram/webhook bildirimleri ve günlük özet de yalnız model
  portföyü izler.

### Kişisel backtest

- `/backtest` her hesaba açıktır. Hesapla girenler kendi koşularını, yerleşik
  (ortam değişkenli) yönetici sistem koşularını görür ve başlatır. Kullanıcı
  koşuları yalnız sahibine görünür; herkese açık `/api/backtests` uçları
  yalnız sistem koşularını döner.
- Koşu artık API isteğinde değil worker'da hesaplanır: önce **Sırada**, sonra
  **Hesaplanıyor**, sonunda **Tamamlandı / Yetersiz veri / Hata**. Sayfa
  sonuç gelene kadar birkaç saniyede bir kendini yeniler.
- Worker'da aynı anda tek backtest çalışır (Redis kilidi); diğerleri sırada
  bekler, collector'lar için iş slotu kalır. Bir saatten uzun sırada kalan
  koşu hatayla kapanır. Worker yeniden başlatıldığı için 2 saatten uzun
  "Sırada/Hesaplanıyor" kalan koşu, bir sonraki koşu ya da kota sorgusunda
  hatayla kapatılır ve kullanıcıyı kilitlemez.
- Kota (yönetici rolü muaf): kullanıcı başına günde
  `BACKTEST_DAILY_LIMIT_PER_USER` (varsayılan 10) koşu ve aynı anda
  `BACKTEST_MAX_ACTIVE_PER_USER` (varsayılan 1) sıradaki ya da çalışan koşu.
- **Bu ayarlarla paper portföy başlat:** tamamlanmış, eşik stratejili ve
  ağırlık simülasyonsuz koşunun eşikleri (giriş/çıkış skoru, güven, kaynak,
  pozisyon sayısı ve ağırlığı, günlük alım, zarar-kes) yeni bir strateji
  portföyüne aktarılır. Komisyon, kayma, tavan/taban ve hacim kuralları paper'da
  herkes için sabittir; kâr-al, takip eden stop ve sektör tavanı kapalı başlar.

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

### Web yük ölçümü (`/sistem` → Web yükü)

`/sistem` sayfasındaki **Web yükü** bölümü, yük altında yavaşlığın nereden
geldiğini ayırmak içindir:

- **Sayfa başına süreler (p50 / p95):** toplam, *API bekleme* (sayfanın API
  yanıt başlıklarını beklediği duvar saati süresi) ve *render* (toplam − API
  bekleme: React render'ı, JSON ayrıştırma, event-loop kuyruğu). API
  çağrılarının süresi API'nin `Server-Timing: app;dur=` başlığıyla
  karşılaştırılır; aradaki fark ağ, uvicorn kuyruğu ve event-loop beklemesidir.
  apiGet önbellek sonuçları (isabet / uçuştakine ortak / ıska) da gösterilir.
- **Web süreçleri:** süreç başına CPU (%100 = bir çekirdek), event-loop
  gecikmesi (`perf_hooks.monitorEventLoopDelay`), bellek ve süren istek sayısı.
- **Host:** yük ortalaması, host / container'ın gördüğü CPU sayısı ve cgroup
  CPU kotası, host CPU meşguliyeti ve *steal* oranı (`/proc/stat`), web
  container'ının CPU kullanımı ve kısılması (cgroup `cpu.stat`).

Kaba yorum: API bekleme yüksek ve API işlem süresi de yüksekse darboğaz API /
veritabanıdır; API işlem süresi düşük ama çağrı süresi yüksekse kuyruk veya
CPU'dur. Host CPU meşguliyeti %90'ı aşıyor veya yük ortalaması CPU sayısını
geçiyorsa host doymuştur. Render ve event-loop gecikmesi yüksekse web
süreçleri CPU'ya doymuştur.

Aynı veri yük testinde `curl` ile okunabilsin diye JSON olarak
`/sistem/metrikler` adresindedir (yönetici oturum çerezi gerekir). Ölçümler
süreç belleğindedir (süreç başına son 500 istek, en çok 5 dakika) ve yalnız
Docker imajı (`server-cluster.cjs`) ile toplanır; `npm run dev` altında
kapalıdır. Herkese açık `/health` CPU/yük bilgisi içermez.

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
| `POST /api/backtests` | Sistem (yönetici) backtest'ini kuyruğa ekleme |
| `POST /api/system/storage/vacuum` | Veritabanı bakım işlemi |
| `/api/auth/*` | Kayıt, giriş, e-posta doğrulama, parola sıfırlama (yalnız web sunucusu çağırır; okuma uçları dahil anahtar ister) |
| `/api/admin/*` | Kullanıcı listesi, kullanıcı durumu/rolü, davet kodları (okuma uçları dahil) |

`/api/auth/*` ve `/api/admin/*` dışındaki okuma (`GET`) uçları anahtar istemez. `GET /api/settings`, gizli değerleri
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
