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
birleştiren sürümlü 0-100 skor motoru tamamlandı.

✅ **Faz 8 — Paper Portföy**: canlı emir göndermeyen, komisyon/kayma içeren,
risk sınırları ve mükerrer işlem koruması olan sanal portföy motoru tamamlandı.

✅ **Dashboard**: mevcut özelliklerin tamamı için responsive Next.js arayüz,
detay ekranları, sayfalama, paper portföy görünümü ve merkezi tema sistemi hazır.

✅ **TCMB Faiz & Makro**: resmî PPK kararları ve yaklaşan toplantılar, faiz
koridoru ve senaryo bazlı piyasa aktarım kanallarıyla izleniyor.

✅ **Tarama Takvimi Yönetimi**: 12 veri/analiz işi `/sistem` ekranından
görüntülenebilir, duraklatılabilir, aralığı değiştirilebilir ve elle çalıştırılabilir.
Ayarlar PostgreSQL'de kalır; Redis kilidi mükerrer worker tetiklemesini önler.

Toplam **99 ağsız test** geçiyor. Docker ile yapılan canlı doğrulamaların
sayısal sonuçları `.claude/CODEX_NOTES.md` içinde.

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

Port çakışmasında `.env` içinde `API_PORT`/`WEB_PORT` ve buna uygun
`NEXT_PUBLIC_API_URL` değiştirilebilir.

## Servisler

| Servis | Ne yapar |
|---|---|
| `postgres` | Kalıcı veri |
| `redis` | Kuyruk, cache, dedup, pub/sub |
| `api` | FastAPI — REST + WebSocket |
| `worker` | ARQ — collector cron job'ları |
| `web` | Next.js dashboard |

## Coolify'a deploy

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
3. ⬜ **Coolify üretim kapısı:** Kalıcı PostgreSQL volume/yedekleme, private ağ,
   health check, migration, restart kalıcılığı ve temiz kurulum smoke testi
   doğrulanacak. API/web/worker stateless kalacak.

Ayrıntılı ve kanonik uygulama sırası `.claude/PROGRESS.md` dosyasındadır.

## Yapı

```
backend/   FastAPI + ARQ worker (tek Python paketi, iki farklı komutla çalışır)
web/       Next.js 15 dashboard
ops/       Caddyfile (yalnızca Coolify dışı self-host için)
```
