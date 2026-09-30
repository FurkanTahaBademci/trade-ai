# trade-ai

BIST için haber/KAP + temel analiz + kurumsal görüş sinyallerini birleştiren
piyasa istihbarat platformu. Çıktı: hisse başına bileşik skor + bu skorla
işletilen kağıt üstü (paper) portföy. **Canlı emir iletimi yoktur.**

Detaylı mimari ve faz planı: [`.claude/CLAUDE.md`](.claude/CLAUDE.md) ve
[`.claude/PROGRESS.md`](.claude/PROGRESS.md) — her yeni oturumda önce bunlara bak.

## Durum

✅ **Faz 0 — İskelet + Kaynak Doğrulama**: kod tarafı tamam, 6/6 veri kaynağı
(KAP liste+detay, TEFAS fon dağılımı, 2 RSS feed, `isyatirimhisse`) gerçek
istekle doğrulandı.

✅ **Faz 1 — Hisse Evreni + Fiyat Verisi**: kod ve gerçek PostgreSQL
entegrasyonu doğrulandı (807 ticker; örnek fiyat akışı x2 idempotent).

✅ **Faz 2-7 — Piyasa İstihbaratı + Bileşik Sinyal**: KAP, haber, Gemini
değerlendirmesi, temel analiz, analist konsensüsü, TEFAS fon akımı ve bunları
birleştiren sürümlü 0-100 skor motoru tamamlandı. Gemini 3.8 Flash,
Interactions API üzerinden yapılandırılmış SSE akışıyla kullanılabilir; API
yolu ve Tier 1/Tier 2 modelleri `/sistem` ekranından seçilir.

✅ **Faz 8 — Paper Portföy**: canlı emir göndermeyen, komisyon/kayma içeren,
risk sınırları ve mükerrer işlem koruması olan sanal portföy motoru tamamlandı.

✅ **Dashboard**: mevcut özelliklerin tamamı için responsive Next.js arayüz,
detay ekranları, Haber/KAP/AI Analiz/Sinyal/Piyasa listelerinde kaydırdıkça
kademeli yükleme, her ekrandan hisse arama, tarayıcı tabanlı izleme listesi,
paper portföy görünümü ve merkezi tema sistemi hazır.

✅ **TCMB Faiz & Makro**: resmî PPK kararları ve yaklaşan toplantılar, faiz
koridoru ve senaryo bazlı piyasa aktarım kanallarıyla izleniyor.

✅ **Tarama Takvimi Yönetimi**: 12 veri/analiz işi `/sistem` ekranından
görüntülenebilir, duraklatılabilir, aralığı değiştirilebilir ve elle çalıştırılabilir.
Ayarlar PostgreSQL'de kalır; Redis kilidi mükerrer worker tetiklemesini önler.

✅ **Operasyonel Veri Kalitesi**: `/sistem` aktif enstrümanların güncel sinyal
kapsamını ve çözülmemiş AI hatalarının secret/ham mesaj göstermeyen kategori
dağılımını raporlar.

✅ **Docker / Coolify Hazırlığı**: servisler health check, kaynak sınırı, log
rotasyonu, salt-okunur dosya sistemi ve yetkisiz kullanıcılarla sertleştirildi.
PostgreSQL/Redis kalıcılığı ile yedekleme, geri yükleme ve üretim smoke komutları hazır.

Toplam **211 backend + 49 web ağsız test** geçiyor. Docker ile yapılan canlı
doğrulamaların sayısal sonuçları `.claude/CODEX_NOTES.md` içinde.

## Hızlı başlangıç (yerel geliştirme)

```bash
cp .env.example .env      # gerekirse degerleri duzenle
make dev                  # docker compose up -d --build
make migrate              # alembic upgrade head
make smoke                # tum veri kaynaklarini dogrula
```

- API: http://localhost:8000/docs
- Dashboard: http://localhost:3000
- Paper portföy: http://localhost:3000/portfoy
- Faiz ve makro: http://localhost:3000/makro

Paper motorunu elle çalıştırmak için:

```bash
docker compose exec api python -m scripts.run_once paper
```

### Arayüz teması

Dashboard renkleri tek noktadan, `web/src/app/globals.css` dosyasının başındaki
`TRADE-AI THEME` CSS değişkenlerinden yönetilir. Marka rengi için `--primary`,
zeminler için `--background` / `--surface`, durum renkleri için
`--positive` / `--negative` değişkenlerini değiştirmek yeterlidir.

Port çakışmasında `.env` içinde `API_PORT`/`WEB_PORT` değiştirilebilir. Web,
backend'e Docker'ın private ağındaki `API_INTERNAL_URL` üzerinden ulaşır.

## Servisler

| Servis | Ne yapar |
|---|---|
| `postgres` | Kalıcı veri |
| `redis` | Kuyruk, cache, dedup, pub/sub |
| `api` | FastAPI — REST + WebSocket |
| `worker` | ARQ — collector cron job'ları |
| `web` | Next.js dashboard |

## Coolify'a deploy

Eksiksiz ortam, yedek, doğrulama ve geri alma adımları:
[Coolify üretim kontrol listesi](ops/COOLIFY.md).

Production değişkenlerini girdikten sonra secret değerlerini göstermeyen yayın
öncesi kontrolü `make preflight` ile çalıştırın.

1. Bu repo'yu Coolify'da "Docker Compose" tipi bir kaynak olarak ekle.
2. `.env.example`'daki değişkenleri Coolify'ın Environment Variables ekranına gir
   (özellikle `POSTGRES_PASSWORD`, `GEMINI_API_KEY`, `N8N_WEBHOOK_URL`).
3. Sadece `api` ve `web` servislerine domain/port ata; `postgres`/`redis`/`worker`
   dışarı açılmamalı.
4. İlk deploy sonrası `api` container'ında migration otomatik çalışır
   (`docker-compose.yml` → `api.command`).

## Sıradaki işler

1. ✅ **Tarama takvimi yönetimi:** Haberlerin varsayılan 5 dakikalık taraması
   dahil 12 iş artık `/sistem` ekranından kalıcı biçimde yönetiliyor.
2. ✅ **Gelişmiş hisse grafikleri:** Çoklu tarih aralığı, hacim, düşük/yüksek
   bandı, AOF, tooltip, MA20/MA50 ve RSI katmanları hisse detayına eklendi.
   Güvenilir açılış verisi bulunmadan sahte mum verisi üretilmiyor.
3. ✅ **Coolify üretim kapısı (kod):** Kalıcı PostgreSQL/Redis volume, yedekleme,
   private ağ, health check, migration, restart kalıcılığı ve temiz kurulum smoke
   testi doğrulandı. Gerçek domain/TLS bağlantısı Coolify erişimiyle yapılacak.
4. ✅ **Gemini kontrollü bağlantı testi:** `/sistem` ekranından seçili Tier 1 veya
   Tier 2 modeli, Interactions/GenerateContent modu ve token kullanımı batch
   değerlendirmesi açılmadan tek küçük istekle doğrulanabiliyor.

Ayrıntılı ve kanonik uygulama sırası `.claude/PROGRESS.md` dosyasındadır.

## Yapı

```
backend/   FastAPI + ARQ worker (tek Python paketi, iki farklı komutla çalışır)
web/       Next.js 16 dashboard
ops/       Coolify işletim/yedek/smoke araçları ve yerel Caddyfile
```
