# trade-ai — Proje Notları

Bu dosya, projeye her yeni oturumda hızlı bağlam kazandırmak için var.
Detaylı faz planı: `C:\Users\furkan\.claude\plans\algoritmik-trade-ve-analiz-logical-blossom.md`
(kullanıcının global plan dizini — bu repo'nun dışında).

## Ne inşa ediyoruz

BIST için haber/KAP + temel analiz + kurumsal görüş (analist tavsiyesi + fon
akımı) sinyallerini birleştiren bir piyasa istihbarat platformu. Çıktı: hisse
başına 0-100 bileşik skor + bu skorla çalışan **kağıt üstü (paper) portföy**.
Canlı emir iletimi **yok** (bilinçli karar — risk yönetimi ve backtest
olgunlaşmadan gerçek para riske atılmayacak).

## Kilit kararlar (değiştirilmeden önce kullanıcıya danışılmalı)

- **LLM:** Gemini API (`google-genai` SDK). Claude değil — kullanıcı özellikle seçti.
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
- **Fiyat/bilanço:** `isyatirimhisse` pip paketi (resmi değil, kişisel kullanım).
- Gemini fiyatları (Eylül 2026 itibarıyla): flash ~$0.75/$3.75, pro ~$2/$4 per
  MTok — **canlıya almadan önce `ai.google.dev/pricing`'den teyit et**, bu
  fiyatlar sık değişiyor.

## Durum takibi

Faz ilerlemesi için `.claude/PROGRESS.md` dosyasına bak — her faz bitince
orada işaretleniyor. Codex'in son uygulama/devir ayrıntıları için ayrıca
`.claude/CODEX_NOTES.md` dosyasını oku. Yeni bir oturuma başlarken önce bu iki
dosyayı incele.

## Vibe coding kuralları (planın 6. bölümünden)

1. Şema önce, kod sonra.
2. Her kaynaktan gerçek yanıt `backend/tests/fixtures/`e kaydedilir.
3. `collectors/base.py` tek doğru yazılır, herkes ondan türer.
4. LLM promptları ayrı dosyada, versiyonlu (`llm/prompts/v1.md`).
5. Idempotency her collector'da test edilir (iki kez çalıştır, ikinci sıfır satır).
6. Bir seferde bir dosya — LLM'e büyük kapsamlı "her şeyi yaz" verilmez.
