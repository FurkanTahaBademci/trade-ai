# Coolify üretim kontrol listesi

## Kaynak ve domain

1. Git deposunu **Docker Compose** kaynak türüyle ekle.
2. `web` servisine ana domaini, gerekirse `api` servisine ayrı API domainini bağla.
   PostgreSQL, Redis ve worker servislerine public port/domain verme.
3. Ana domain aynı origin üzerinden `/api` proxy'leyecekse `NEXT_PUBLIC_API_URL`
   değerini ana domaine; ayrı API domaini kullanılıyorsa API'nin HTTPS adresine ayarla.

## Zorunlu production değişkenleri

- `ENVIRONMENT=production`
- Güçlü ve benzersiz `POSTGRES_PASSWORD`
- Parolayla eşleşen tam `DATABASE_URL`
- En az 32 rastgele karakterli `ADMIN_API_TOKEN` (API ve web aynı değeri alır)
- `NEXT_PUBLIC_API_URL=https://api.example.com` veya aynı-origin adresi
- `CORS_ORIGINS=https://app.example.com` (birden çoksa virgülle ayır)
- `ALLOWED_HOSTS=api.example.com,api,localhost`
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

1. `docker compose config --quiet` ile birleşik Compose yapılandırmasını doğrula.
2. API açılışta `alembic upgrade head` çalıştırır; worker API health başarılı
   olmadan başlamaz.
3. Tüm servislerin healthy olduğunu ve migration head'ini kontrol et:
   `docker compose ps` ve `docker compose exec -T api alembic current`.
4. Domainler açıldıktan sonra:
   `WEB_URL=https://app.example.com API_URL=https://api.example.com make production-smoke`.
5. `/sistem` ekranında worker, PostgreSQL, Redis ve veri hatlarının durumunu kontrol et.

## Geri alma

- Uygulama image'ını önceki commit'e döndürmeden önce migration'ın geriye uyumlu
  olduğunu kontrol et. Veri kaybı riski taşıyan `alembic downgrade` yerine doğrulanmış
  PostgreSQL yedeğinden yeni bir test veritabanına geri yüklemeyi tercih et.
- Sorun yalnız collector'daysa `/sistem` üzerinden ilgili takvimi duraklat; API ve
  dashboard'u kapatmadan veri toplamayı izole edebilirsin.
