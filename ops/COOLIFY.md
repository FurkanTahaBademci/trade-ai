# Coolify üretim kontrol listesi

## Kaynak ve domain

1. Git deposunu **Docker Compose** kaynak türüyle ekle.
2. `web` servisine ana domaini bağla. Web, API'ye private Docker ağı üzerinden
   erişir; PostgreSQL, Redis, worker ve API'ye public port/domain vermek gerekmez.
3. API'yi harici istemcilere açacaksan ayrı bir HTTPS domaini bağla. Cloudflare'ın
   standart wildcard sertifikası genellikle yalnız tek alt-domain seviyesini
   kapsadığı için `api.app.example.com` yerine `api-app.example.com` gibi sertifika
   kapsamındaki bir ad kullan veya o hostname'i kapsayan sertifika tanımla.

## Zorunlu production değişkenleri

- `ENVIRONMENT=production`
- Güçlü ve benzersiz `POSTGRES_PASSWORD`
- Parolayla eşleşen tam `DATABASE_URL`
- En az 32 rastgele karakterli `ADMIN_API_TOKEN` (API ve web aynı değeri alır)
- `/sistem` ve `/backtest` için güçlü `WEB_ADMIN_PASSWORD` (kullanıcı adı
  varsayılan `admin`, `WEB_ADMIN_USERNAME` ile değiştirilebilir)
- `CORS_ORIGINS=https://app.example.com` (birden çoksa virgülle ayır)
- `ALLOWED_HOSTS=api,localhost` (public API varsa domainini de ekle)
- İhtiyaca göre Gemini ve N8N değişkenleri

Secret değerlerini repoya veya image build argümanına koyma; Coolify Environment
Variables/Secrets alanında runtime değişkeni olarak tut.

## Veri kalıcılığı ve yedek

- Compose içindeki `postgres_data` ve `redis_data` named volume'lerini kalıcı
  storage olarak doğrula. Deploy sırasında volume silme seçeneğini kullanma.
- İlk canlı veri öncesi ve her migration öncesi PostgreSQL yedeği al. Sunucuda
  `make backup` komutu özel formatlı dump üretir; dosyayı sunucu dışında şifreli
  bir hedefe kopyala.
- Geri yüklemeyi önce ayrı test ortamında doğrula:
  `CONFIRM_RESTORE=trade-ai make restore FILE=backups/trade-ai-....dump`.
- Coolify planın destekliyorsa zamanlanmış S3-uyumlu database backup ve retention
  tanımla; yalnız sunucudaki tek volume bir yedek değildir.

## Dağıtım ve doğrulama

1. Production değişkenlerini girdikten sonra `make preflight` çalıştır. Bu komut
   secret değerlerini ekrana basmadan zorunlu ayarları ve birleşik Compose
   yapılandırmasını doğrular.
2. API açılışta `alembic upgrade head` çalıştırır; worker API health başarılı
   olmadan başlamaz.
3. Tüm servislerin healthy olduğunu ve migration head'ini kontrol et:
   `docker compose ps` ve `docker compose exec -T api alembic current`.
4. Domainler açıldıktan sonra public API kullanıyorsan:
   `WEB_URL=https://app.example.com API_URL=https://api-app.example.com make production-smoke`.
   API private kalıyorsa web için `/health`, ana sayfalar ve KAP ek indirme
   rotasını kontrol et; API/DB health'i Coolify container health durumundan izle.
5. `/sistem` ekranında worker, PostgreSQL, Redis ve veri hatlarının durumunu kontrol et.

### Sağlık kontrolleri

- `/health` yalnız API sürecini, `/health/ready` PostgreSQL ve Redis erişimini
  kontrol eder. Hazır olmayan API `/health/ready` için HTTP 503 döndürür.
- `/health/detailed` arayüzün sorunları gösterebilmesi için HTTP 200 dönebilir;
  gövdedeki `status` alanını da kontrol et. `make production-smoke` bunu yapar
  ve `degraded` / `pending` durumunda başarısız olur; host üzerinde `python3`
  ve `curl` gerektirir.
- Worker Docker kontrolü `arq ... --check` kullanır; worker sağlık anahtarını
  30 saniyede bir yeniler. Redis'in tek başına ayakta olması yeterli değildir.
- API başlangıcında otomatik `VACUUM FULL` çalıştırılmaz. Bu işlem tabloyu
  kilitleyebildiğinden yalnız gerektiğinde bakım penceresinde elle çalıştırılır.

### Yönetim ekranı erişimi

`ADMIN_API_TOKEN`, backend yazma uçlarını; `/giris` sayfasındaki yönetici girişi
ise `/sistem` ve `/backtest` sayfalarıyla bunların Server Action POST isteklerini korur. Ayrı
`WEB_ADMIN_PASSWORD` önerilir; boşsa geçiş uyumluluğu için `ADMIN_API_TOKEN`
parola olur. Coolify/reverse proxy üzerinde ek erişim kontrolü kullanılabilir.

Parola üretme, giriş, parola değiştirme ve sorun giderme adımları:
[docs/ADMIN.md](../docs/ADMIN.md). Değerleri üretmek için:
`openssl rand -hex 32` (`ADMIN_API_TOKEN`), `openssl rand -hex 16`
(`WEB_ADMIN_PASSWORD`), `openssl rand -hex 24` (`POSTGRES_PASSWORD`).

## Geri alma

- Uygulama image'ını önceki commit'e döndürmeden önce migration'ın geriye uyumlu
  olduğunu kontrol et. Veri kaybı riski taşıyan `alembic downgrade` yerine doğrulanmış
  PostgreSQL yedeğinden yeni bir test veritabanına geri yüklemeyi tercih et.
- Sorun yalnız collector'daysa `/sistem` üzerinden ilgili takvimi duraklat; API ve
  dashboard'u kapatmadan veri toplamayı izole edebilirsin.
