# trade-ai — Proje Notları

Bu dosya, yapay zeka kodlama asistanlarına (Claude Code vb.) projede hızlı
bağlam kazandırmak için var. İnsan katkıcılar için asıl rehber
`CONTRIBUTING.md`'dir.

## Ne inşa ediyoruz

BIST için haber/KAP + temel analiz + kurumsal görüş (analist tavsiyesi + fon
akımı) sinyallerini birleştiren bir piyasa istihbarat platformu. Çıktı: hisse
başına 0-100 bileşik skor + bu skorla çalışan **kağıt üstü (paper) portföy**.
Canlı emir iletimi **yok** (bilinçli karar — risk yönetimi ve backtest
olgunlaşmadan gerçek para riske atılmayacak).

## Kilit kararlar (değiştirilmeden önce bakımcıya danışılmalı)

- **LLM:** Gemini API (`google-genai` SDK) — bilinçli tercih, başka sağlayıcıya geçilmez.
- **Hisse evreni:** Tüm BIST (~600 hisse), ama derin işlemler (LLM Katman 2,
  temel analiz) maliyet nedeniyle filtrelenmiş alt kümede çalışır.
- **Analist verisi:** Tek bir temiz API yok. Üç kaynak paralel: kurum PDF'leri
  (en güvenilir) + agregatör siteler (kırılgan) + TEFAS fon akımı (resmi).
- **Deployment:** Coolify + Docker Compose, tek repo. Servisler: postgres,
  redis, api (FastAPI), worker (ARQ), web (Next.js).
- **Idempotency zorunlu:** Her collector aynı işi iki kez çalıştırıldığında
  sıfır yeni satır üretmeli (`ON CONFLICT` ile).

## Doğrulanmış teknik detaylar (tekrar araştırmaya gerek yok)

- **KAP liste:** `POST kap.org.tr/tr/api/disclosure/members/byCriteria`,
  `Referer: .../tr/bildirim-sorgu` + `User-Agent` zorunlu, max 2000 kayıt/istek.
- **KAP detay:** `GET /tr/api/notification/attachment-detail/{disclosureIndex}`.
- **KAP PDF eki:** `GET /tr/api/file/download/{objId}` — **ham PDF değil**,
  Java-serialized `byte[]` sarmalayıcı (magic `AC ED 00 05`). Çözmeden
  kullanılamaz.
- **TEFAS:** `tefas.gov.tr/api/...` resmi Takasbank API'si, en temiz kaynak.
  Faz 0 smoke script'inde tam endpoint doğrulanıyor.
- **Fiyat/bilanço:** `isyatirimhisse` pip paketi (resmi olmayan istemci).
- Gemini fiyatları (Eylül 2026 itibarıyla): flash ~$0.75/$3.75, pro ~$2/$4 per
  MTok — **canlıya almadan önce `ai.google.dev/pricing`'den teyit et**, bu
  fiyatlar sık değişiyor.

## Durum takibi

Bakımcının yerel ilerleme notları varsa `.claude/PROGRESS.md` ve
`.claude/CODEX_NOTES.md` dosyalarındadır (git'e girmez, her klonda olmayabilir).
Yayınlanmış değişikliklerin listesi `CHANGELOG.md`'dedir.

## Proje kuralları (ayrıntı: CONTRIBUTING.md)

1. Şema önce, kod sonra.
2. Her kaynaktan gerçek yanıt `backend/tests/fixtures/`e kaydedilir.
3. `collectors/base.py` tek doğru yazılır, herkes ondan türer.
4. LLM promptları ayrı dosyada, versiyonlu (`llm/prompts/v1.md`).
5. Idempotency her collector'da test edilir (iki kez çalıştır, ikinci sıfır satır).
6. Bir seferde bir dosya — LLM'e büyük kapsamlı "her şeyi yaz" verilmez.

## Açık kaynak

- Repo **public**. Canlı domain, sunucu IP'si, kişisel yol/e-posta veya gerçek
  secret yazma. Canlı ortam gözlemleri git dışı `ops/LIVE-REVIEW-*.md`
  dosyalarına yazılır (.gitignore).
- Kod yorumlarında git dışı `.claude/` notlarına atıf yapma.
- Commit öncesi `make leak-check`; CI aynı denetimi çalıştırır.
- Kullanıcıyı etkileyen her değişiklik `CHANGELOG.md` → `[Unreleased]`'e
  eklenir. Sürüm: `make release VERSION=X.Y.Z` (tek kaynak `VERSION`,
  ayrıntı `docs/RELEASING.md`).
- Yeni env değişkeni → `.env.example` + `docs/CONFIGURATION.md`.
