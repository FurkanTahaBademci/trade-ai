# trade-ai

Borsa İstanbul (BIST) için açık kaynak bir piyasa istihbarat platformu. KAP
bildirimlerini, ekonomi haberlerini, temel analizi, analist görüşlerini ve TEFAS
fon akımlarını toplar. Yapay zekayla değerlendirir, hisse başına 0–100 arası
bileşik bir skor üretir ve bu skorla çalışan **sanal (paper) bir portföy**
işletir.

> [!WARNING]
> **Yatırım tavsiyesi değildir.** Bu yazılım araştırma ve eğitim amaçlıdır.
> Üretilen skorlar, sinyaller ve portföy sonuçları hatalı veya eksik olabilir.
> Sistem **gerçek emir iletmez**; aracı kurumlara bağlanmaz. Yazılımı kullanarak
> aldığınız kararların sorumluluğu size aittir (bkz. [LICENSE](LICENSE)).

## Özellikler

- **Veri toplama:** KAP bildirimleri ve PDF ekleri, 6 ekonomi haber kaynağı
  (RSS), günlük fiyatlar ve BIST100, bilanço kalemleri, analist hedef fiyatları,
  kurum araştırma raporları, TEFAS fon dağılımları ve TCMB para politikası
  kararları. Her toplayıcı idempotenttir: aynı iş iki kez çalıştığında mükerrer
  kayıt oluşmaz.
- **Yapay zeka değerlendirmesi (opsiyonel):** Gemini ile iki aşamalı
  sınıflandırma. Önce ucuz bir model tüm kaynakları tarar, yüksek etkili olanlar
  daha güçlü bir modelle ikinci kez incelenir. Varsayılan olarak kapalıdır;
  günlük token bütçesiyle korunur.
- **Bileşik sinyal:** Haber/KAP duygusu, temel analiz, analist konsensüsü ve fon
  akımını birleştiren sürümlü 0–100 skor, skor geçmişi ve isabet ölçümü.
- **Paper portföy ve backtest:** Komisyon ve kayma hesaplı sanal portföy;
  stop-loss, take-profit, takip eden stop ve ağırlık sınırları. Stratejinin
  geçmiş veride BIST100'e karşı testi.
- **Dashboard:** Piyasalar, sinyaller, haberler, KAP, AI analizleri, kurumsal
  görüş, makro/faiz, piyasa takvimi, hisse karşılaştırma, izleme listesi,
  portföy ve CSV dışa aktarma. Açık/koyu tema ve mobil uyumlu arayüz.
- **Yönetim:** Tarama takvimi, çalışma zamanı ayarları, bildirimler
  (Telegram/webhook) ve veri kalitesi izleme. Hepsi parola korumalı `/sistem`
  ekranından yönetilir.

## Mimari

```
                ┌──────────────┐
  Tarayıcı ───▶ │ web (Next.js)│ ──┐  iç Docker ağı
                └──────────────┘   ▼
                            ┌──────────────┐     ┌────────────┐
                            │ api (FastAPI)│ ──▶ │ PostgreSQL │
                            └──────────────┘     └────────────┘
                                   │                   ▲
                                   ▼                   │
                             ┌─────────┐   iş   ┌──────────────┐
                             │  Redis  │ ◀────▶ │ worker (ARQ) │ ──▶ KAP, RSS, TEFAS,
                             └─────────┘        └──────────────┘     İş Yatırım, Gemini…
```

| Servis | Görev |
|---|---|
| `postgres` | Kalıcı veri |
| `redis` | İş kuyruğu, kilitler, önbellek, çalışma zamanı ayarları |
| `api` | FastAPI REST API; açılışta veritabanı migration'larını çalıştırır |
| `worker` | ARQ: zamanlanmış veri toplama, değerlendirme ve portföy işleri |
| `web` | Next.js dashboard; API'ye yalnız iç ağdan erişir |

```
backend/   FastAPI + ARQ worker (tek Python paketi, iki ayrı komut)
web/       Next.js dashboard
ops/       Kurulum, yedekleme, ön kontrol ve sürüm betikleri
docs/      Yapılandırma ve yönetim dokümanları
```

## Hızlı başlangıç

Gereksinimler: Docker (Compose v2), `make`, `openssl` veya `python3`.

```bash
git clone <bu-repo> trade-ai && cd trade-ai
make init       # güçlü parolalarla .env üretir ve yönetim girişini yazdırır
make dev        # tüm servisleri derleyip başlatır
```

- Dashboard: <http://localhost:3000>
- API dokümanı: <http://localhost:8000/docs>
- Yönetim: <http://localhost:3000/sistem>. Tarayıcı, `make init` çıktısındaki
  kullanıcı adı ve parolayı sorar.

Veritabanı migration'ları API açılırken otomatik çalışır. İlk veriler worker'ın
takvimine göre birkaç dakika içinde gelmeye başlar. Beklemek istemiyorsanız bir
işi `/sistem` ekranından elle çalıştırabilir veya komut satırını
kullanabilirsiniz:

```bash
docker compose exec api python -m scripts.run_once instruments   # hisse evreni
docker compose exec api python -m scripts.run_once paper         # paper portföy
make smoke                                                      # dış kaynakları test et
```

Yapay zeka değerlendirmesini açmak için `/sistem` → Ayarlar bölümüne Gemini API
anahtarınızı girin ve "LLM Degerlendirmesi Etkin" ayarını açın.

## Dokümantasyon

| Doküman | İçerik |
|---|---|
| [docs/ADMIN.md](docs/ADMIN.md) | Yönetim girişi, parolaların üretilmesi ve değiştirilmesi, sorun giderme |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Tüm ortam değişkenleri ve `/sistem` ayarları |
| [ops/COOLIFY.md](ops/COOLIFY.md) | Production kurulumu (Coolify / Docker Compose), yedekleme, geri alma |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Geliştirme ortamı, testler, proje kuralları |
| [CHANGELOG.md](CHANGELOG.md) | Sürüm notları |
| [docs/RELEASING.md](docs/RELEASING.md) | Sürümleme, yayın ve sızıntı denetimi |
| [SECURITY.md](SECURITY.md) | Güvenlik açığı bildirimi |

## Production'a kurulum

Kısaca: repoyu Coolify'da (veya herhangi bir Docker Compose sunucusunda) kaynak
olarak ekleyin, production değişkenlerini girin ve yalnız `web` servisine domain
bağlayın. Ardından `make preflight` çalıştırın; bu komut zayıf veya eksik
ayarları secret değerlerini göstermeden yakalar. Adım adım kontrol listesi:
[ops/COOLIFY.md](ops/COOLIFY.md).

Coolify dışında bir sunucuda TLS için örnek reverse proxy yapılandırması:
[`ops/Caddyfile`](ops/Caddyfile).

## Geliştirme

```bash
# Backend
cd backend && pip install -e ".[dev]"
ruff check app tests scripts && pytest -q

# Web
cd web && npm ci
npm run lint && npm test && npm run build
```

Testler ağa ve veritabanına bağlanmadan, `backend/tests/fixtures/` altındaki
gerçek kaynak örnekleriyle çalışır. Ayrıntılar: [CONTRIBUTING.md](CONTRIBUTING.md).

Arayüz renkleri `web/src/app/globals.css` başındaki tema değişkenlerinden
yönetilir (`--primary`, `--background`, `--positive`, `--negative`…).

## Sürümler

Sürüm numarası kök dizindeki [`VERSION`](VERSION) dosyasındadır ve
[Semantic Versioning](https://semver.org/lang/tr/) kurallarını izler. Çalışan
sürüm `GET /health` yanıtında görünür. Değişiklikler
[CHANGELOG.md](CHANGELOG.md) dosyasında listelenir.

## Veri kaynakları

trade-ai; KAP, TEFAS, TCMB, İş Yatırım (`isyatirimhisse` paketi), haber
sitelerinin RSS akışları ve kurum araştırma sayfaları gibi herkese açık
kaynaklardan veri okur. Bu kaynakların hiçbiri projeyle bağlantılı değildir.
Kaynakların kullanım koşullarına uymak ve istek hızını makul tutmak
(`KAP_RATE_LIMIT_PER_SEC`) kullanıcının sorumluluğundadır. Resmî olmayan uç
noktalar haber verilmeden değişebilir.

`backend/tests/fixtures/` altındaki örnek yanıtlar yalnızca otomatik testler
için tutulan kısa alıntılardır. Telif hakları ilgili kaynak sahiplerine aittir.

## Lisans

[MIT](LICENSE)
