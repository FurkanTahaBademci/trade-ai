# Fixtures

Bu dizindeki dosyalar, gercek kaynaklardan (KAP, TEFAS, RSS) alinan **gercek**
yanitlarin donduruldugu anlardaki kopyalaridir. Amac: collector/parser testleri
agdaki servislere baglanmadan, gercekci veriyle calisabilsin (bkz. proje
"vibe coding" kurali #2 — `.claude/CLAUDE.md`).

| Dosya | Kaynak | Alindigi tarih |
|---|---|---|
| `kap/disclosure_list_sample.json` | `POST /tr/api/disclosure/members/byCriteria` (ilk 10 kayit) | 2026-09-06 |
| `kap/disclosure_detail_sample.json` | `GET /tr/api/notification/attachment-detail/{index}` | 2026-09-06 |
| `tefas/dagilim_sample.json` | `POST /api/funds/dagilimSiraliGetirT` (10 satir) | 2026-09-06 |
| `rss/bloomberght_sample.xml` | `bloomberght.com/rss` (ham XML) | 2026-09-06 |
| `rss/investing_tr_sample.xml` | `tr.investing.com/rss/news.rss` (ham XML) | 2026-09-06 |

**Not:** Kaynaklarin semasi degisirse (yeni alan, kaldirilan alan, farkli
sarmalayici) bu dosyalar guncellenmeli — `backend/scripts/smoke_sources.py`
zaten calisiyorsa, o script'in icindeki istek kodunu kullanip yeni bir ornek
kaydetmek yeterli. Eski ornegi silme; parser'in geriye donuk uyumlulugunu da
test etmek isteyebilirsin.
