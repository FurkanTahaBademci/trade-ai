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
| `rss/aa_ekonomi_sample.xml` | `aa.com.tr/tr/rss/default?cat=ekonomi` (ham XML) | 2026-09-08 |
| `rss/dunya_sample.xml` | `dunya.com/rss?sfid=1` (ham XML) | 2026-09-08 |
| `rss/foreks_sample.xml` | `foreks.com/rss` (ham XML, 100 gercek satirdan ilk 15'i) | 2026-09-08 |
| `financials/thyao_2025_sample.json` | İş Yatırım `MaliTablo` (147 satırdan analizde kullanılan 14 gerçek kalem) | 2026-09-07 |
| `analysts/isyatirim_tracking_sample.html` | İş Yatırım takip listesi (3 gerçek satıra küçültülmüş) | 2026-09-07 |
| `analysts/halkaarz_targets_sample.html` | Halka Arz Takvimi hedef fiyat listesi (4 gerçek satıra küçültülmüş) | 2026-09-07 |
| `tefas/flow_sample.json` | TEFAS genel bilgi + dağılım (2 fon, 2 gerçek gün) | 2026-09-07 |
| `institutional_reports/phillipcapital_listing_sample.html` | PhillipCapital `arastirma-urunleri?category=Şirket Raporları` (4 gerçek rapor kartı + sayfalama) | 2026-09-07 |
| `institutional_reports/eregl_tr_page1.txt` | PhillipCapital EREGL şirket güncelleme raporu PDF'i, sayfa 1 (`pdftotext -layout`, TR şablon) | 2026-09-07 |
| `institutional_reports/eregl_en_page1.txt` | Aynı EREGL raporunun İngilizce sürümü, sayfa 1 | 2026-09-07 |
| `institutional_reports/astor_tr_page1.txt` | PhillipCapital ASTOR kapsama başlangıç raporu, sayfa 1 | 2026-09-07 |
| `institutional_reports/kmpur_meeting_note_page1.txt` | PhillipCapital "Toplantı Notu" (yapısal hedef fiyat tablosu yok — atlanma senaryosu), sayfa 1 | 2026-09-07 |

**Not:** Kaynaklarin semasi degisirse (yeni alan, kaldirilan alan, farkli
sarmalayici) bu dosyalar guncellenmeli — `backend/scripts/smoke_sources.py`
zaten calisiyorsa, o script'in icindeki istek kodunu kullanip yeni bir ornek
kaydetmek yeterli. Eski ornegi silme; parser'in geriye donuk uyumlulugunu da
test etmek isteyebilirsin.
