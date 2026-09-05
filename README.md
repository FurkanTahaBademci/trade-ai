# trade-ai

BIST için haber/KAP + temel analiz + kurumsal görüş sinyallerini birleştiren
piyasa istihbarat platformu. Çıktı: hisse başına bileşik skor + bu skorla
işletilen kağıt üstü (paper) portföy. **Canlı emir iletimi yoktur.**

Detaylı mimari ve faz planı: [`.claude/CLAUDE.md`](.claude/CLAUDE.md) ve
[`.claude/PROGRESS.md`](.claude/PROGRESS.md).

## Hızlı başlangıç (yerel geliştirme)

```bash
cp .env.example .env      # gerekirse degerleri duzenle
make dev                  # docker compose up -d --build
make migrate              # alembic upgrade head
make smoke                # tum veri kaynaklarini dogrula
```

- API: http://localhost:8000/docs
- Dashboard: http://localhost:3000

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

## Yapı

```
backend/   FastAPI + ARQ worker (tek Python paketi, iki farklı komutla çalışır)
web/       Next.js 15 dashboard
ops/       Caddyfile (yalnızca Coolify dışı self-host için)
```
