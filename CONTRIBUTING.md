# Katkı Rehberi

Katkılarınız memnuniyetle karşılanır. Hata bildirimi, öneri veya pull request
göndermeden önce bu sayfayı okuyun.

## Başlamadan önce

- Büyük bir değişiklik için önce bir issue açıp yaklaşımı konuşalım.
- Güvenlik açıklarını issue olarak **açmayın**; bkz. [SECURITY.md](SECURITY.md).
- Canlı emir iletimi (aracı kuruma gerçek emir gönderme) bu projenin kapsamı
  dışındadır ve bu yöndeki PR'lar kabul edilmez.

## Geliştirme ortamı

En kolayı Docker'dır:

```bash
make init && make dev
```

Servisleri Docker dışında çalıştırmak için Python 3.12+ ve Node.js 22 gerekir:

```bash
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cd ../web && npm ci
```

## Testler

Pull request'ten önce şunların geçtiğinden emin olun. CI aynı adımları çalıştırır.

```bash
# backend/
ruff check app tests scripts
pytest -q
alembic upgrade head --sql > /dev/null     # migration'lar SQL üretebiliyor mu

# web/
npm run lint        # TypeScript tip kontrolü
npm test
npm run build
```

Testler ağa ve gerçek veritabanına bağlanmaz. `live` işaretli testler ağ
gerektirir ve varsayılan olarak çalışmaz.

## Proje kuralları

1. **Önce şema, sonra kod.** Yeni bir tablo, Alembic migration'ı
   (`backend/alembic/versions/`) ve SQLAlchemy modeliyle başlar.
2. **Gerçek yanıt örnekleri.** Yeni bir veri kaynağı eklerken kaynaktan alınmış
   gerçek, kısaltılmış bir yanıtı `backend/tests/fixtures/` altına kaydedin ve
   tabloya ekleyin ([fixtures/README.md](backend/tests/fixtures/README.md)).
   Kişisel veri (isim, e-posta, telefon) içeren kısımları ayıklayın.
3. **Tek taban sınıf.** Tüm toplayıcılar `backend/app/collectors/base.py`
   içindeki sınıftan türer. Retry, hız sınırı ve sağlık raporlaması orada
   tanımlıdır; bunları tekrar yazmayın.
4. **Sürümlü promptlar.** LLM promptları kodun içinde değil,
   `backend/app/llm/prompts/` altında sürümlü dosyalarda durur. Prompt değişirse
   yeni sürüm dosyası açılır.
5. **Idempotency zorunlu.** Her toplayıcı aynı veriyle iki kez çalıştırıldığında
   ikinci çalışma sıfır yeni satır üretmelidir (`ON CONFLICT`). Bunu test edin.
6. **Ayarlar tek yerden.** Yeni ayarlar `backend/app/core/config.py` içine
   eklenir; kodda doğrudan `os.environ` okunmaz. Yeni ortam değişkenini
   `.env.example` ve [docs/CONFIGURATION.md](docs/CONFIGURATION.md) dosyalarına
   da ekleyin.
7. **Secret'lar asla repoya girmez.** `.env`, API anahtarları ve token'lar
   commit'lenmez; loglara ve hata mesajlarına da yazılmaz.

## Pull request

- Bir PR tek bir konuyu ele almalıdır.
- Kullanıcıyı etkileyen değişiklikleri [CHANGELOG.md](CHANGELOG.md) dosyasında
  `[Unreleased]` başlığının altına ekleyin.
- Commit mesajlarında kısa, emir kipinde bir başlık kullanın (ör.
  `feat: add TEFAS fund flow chart`, `fix(kap): handle empty attachment`).

Commit'lemeden önce `make leak-check` çalıştırın; CI aynı sızıntı taramasını
yapar. Sürüm süreci: [docs/RELEASING.md](docs/RELEASING.md).

Katkıda bulunarak katkınızın projenin [MIT lisansı](LICENSE) altında
yayınlanmasını kabul etmiş olursunuz.
