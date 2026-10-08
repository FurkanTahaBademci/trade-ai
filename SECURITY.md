# Güvenlik Politikası

## Desteklenen sürümler

Güvenlik düzeltmeleri yalnızca en son yayınlanan sürüm için yapılır.

## Açık bildirme

Bir güvenlik açığı bulduysanız lütfen **herkese açık issue açmayın**.

GitHub'da bu reponun **Security → Report a vulnerability** sekmesinden özel
bildirim gönderin. Bildiriminizde şunlar yer alsın:

- Açığın kısa tanımı ve etkisi
- Yeniden üretme adımları veya kavram kanıtı
- Etkilenen sürüm (`VERSION` dosyası veya `GET /health` yanıtı)

Bildirimler genellikle bir hafta içinde yanıtlanır. Düzeltme yayınlanana kadar
ayrıntıları paylaşmamanızı rica ederiz.

## Kurulum güvenliği

Kendi kurulumunuzu güvenli tutmak için [docs/ADMIN.md](docs/ADMIN.md) ve
[ops/COOLIFY.md](ops/COOLIFY.md) belgelerindeki adımları izleyin. En azından:

- Parolaları `make init` ile üretin. `.env` dosyasını asla paylaşmayın veya
  commit'lemeyin.
- İnternete açık kurulumlarda `ENVIRONMENT=production` ayarlayın ve HTTPS
  kullanın.
- `make preflight` kontrolünün geçtiğinden emin olun.
- PostgreSQL, Redis ve worker servislerine dışarıdan port açmayın.
