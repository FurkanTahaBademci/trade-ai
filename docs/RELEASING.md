# Sürümleme ve Yayın

## Sürüm numarası

Sürümün tek kaynağı kök dizindeki [`VERSION`](../VERSION) dosyasıdır.
`backend/pyproject.toml` ve `web/package.json` dosyaları ona eşitlenir.

Çalışan sürüm şuralarda görünür:

| Yer | Örnek | Kaynak |
|---|---|---|
| Sol menünün en altı | `v0.3.0  abc1234` | Web derlemesi (`package.json` + commit) |
| Web `GET /health` | `{"version": "0.3.0", "commit": "abc1234"}` | Web derlemesi |
| API `GET /health` ve `/health/detailed` | aynı biçim | Backend paketi + `SOURCE_COMMIT` |
| `/sistem` başlığı | `v0.3.0`; web ve API farklıysa uyarı | İkisinin karşılaştırması |

Kısa commit, SemVer'in derleme üst verisi olarak okunur (`0.3.0+abc1234`).
Docker imajı commit bilgisini `SOURCE_COMMIT` build argümanından alır
(`docker-compose.yml`); `make dev` bunu yerelde `git` ile doldurur. Coolify'da
**General → Build → "Include Source Commit in Build"** açık değilse yalnız
sürüm numarası görünür. İmajlarda ayrıca OCI etiketleri
(`org.opencontainers.image.revision` vb.) bulunur.

Web derlemesi sürüm ve commit'ten bir `deploymentId` üretir. Yeni sürüm
yayınlandığında açık sekmeler eski JavaScript ile çalışmaya devam etmez; ilk
gezinmede sayfa tamamen yenilenir.

Sürümleme [Semantic Versioning](https://semver.org/lang/tr/) kurallarını izler:

| Değişiklik | Örnek | Artan |
|---|---|---|
| Geriye uyumsuz (API, veritabanı şeması, zorunlu yeni `.env` ayarı) | 0.4.2 → 1.0.0 | MAJOR |
| Yeni özellik | 0.4.2 → 0.5.0 | MINOR |
| Hata düzeltme | 0.4.2 → 0.4.3 | PATCH |

1.0.0'dan önce MINOR artışı da uyumsuz değişiklik içerebilir. Bu durum
CHANGELOG'da belirtilir.

## Günlük geliştirme

- Kullanıcıyı etkileyen her değişiklik [`CHANGELOG.md`](../CHANGELOG.md) içinde
  `[Unreleased]` başlığının altına yazılır (Eklendi / Değişti / Düzeltildi /
  Kaldırıldı).
- `main`'e her push'ta ve her PR'da CI çalışır: sızıntı taraması, backend
  testleri ve web derlemesi.
- Commit'lemeden önce `make leak-check` ile yerelde aynı taramayı
  çalıştırabilirsiniz.

## Yeni sürüm çıkarma

```bash
make release VERSION=0.2.0
git push origin main --follow-tags
```

`make release` şunları yapar:

1. Çalışma ağacının temiz olduğunu, `main` dalında olduğunuzu ve yeni sürümün
   eskisinden büyük olduğunu kontrol eder.
2. `VERSION`, `backend/pyproject.toml` ve `web/package.json` (+ lock) içindeki
   sürümü günceller.
3. CHANGELOG'daki `[Unreleased]` bölümünü `[0.2.0] - <tarih>` olarak kapatır.
   Bölüm boşsa durur.
4. `chore(release): v0.2.0` commit'ini ve `v0.2.0` etiketini oluşturur. Push
   etmez.

Etiket push edilince [`release.yml`](../.github/workflows/release.yml) tüm CI
adımlarını yeniden çalıştırır. Hepsi geçerse CHANGELOG bölümünü sürüm notu
olarak kullanarak GitHub Release oluşturur ve yapılandırıldıysa sürümü canlıya
alır (aşağıda). `VERSION` dosyasıyla uyuşmayan bir etiket reddedilir.

Yayından sonra sol menüde yeni sürüm numarasını ve `/sistem` başlığında
uyuşmazlık uyarısı olmadığını kontrol edin.

## Canlıya yalnız sürüm çıkarma (Coolify)

Varsayılan Coolify kurulumu `main`'e her push'ta dağıtım yapar; canlıda
yayınlanmamış kod çalışabilir. Canlıya yalnız testlerden geçmiş, etiketli
sürümlerin çıkması için:

1. Coolify'da uygulamanın **Auto Deploy** seçeneğini kapatın.
2. **Webhooks** sekmesindeki deploy URL'sini ve **Keys & Tokens → API tokens**
   altında oluşturduğunuz "Deploy" yetkili token'ı GitHub repo secret'ı olarak
   ekleyin (Settings → Secrets and variables → Actions):
   - `COOLIFY_DEPLOY_WEBHOOK`
   - `COOLIFY_API_TOKEN`
3. **General → Build → "Include Source Commit in Build"** seçeneğini açın
   (sol menüde commit görünür).

Secret'lar tanımlı değilse iş akışındaki "Canlıya al" adımı atlanır; davranış
eskisi gibidir.

Coolify, yapılandırılmış dalın (`main`) o anki son commit'ini dağıtır. Sürüm
etiketini push ettikten sonra iş akışı bitene kadar `main`'e başka commit
push etmeyin; yoksa canlıya sürüm commit'i yerine daha yeni bir commit çıkar.
Sol menüdeki kısa commit, etiketin commit'iyle (`git rev-parse --short vX.Y.Z`)
aynı olmalıdır.

Yanlış bir etiketi geri almak için:

```bash
git tag -d v0.2.0 && git push origin :refs/tags/v0.2.0
```

## Sızıntı denetimi

[`ops/leak-check.sh`](../ops/leak-check.sh), commit'lenebilecek tüm dosyalarda
şunları arar:

- Yasaklı dosyalar: `.env`, `*.pem`, `*.key`, SSH anahtarları, veritabanı
  dökümleri.
- Genel desenler: kişisel dizin yolları, Gmail adresleri, Google API
  anahtarları, özel anahtar blokları.
- Kişiye özel desenler: canlı alan adınız, sunucu IP'niz gibi değerler. Bunlar
  repoya yazılmaz, iki yerden okunur:
  - CI: repo secret'ı `LEAK_DENY_PATTERNS` (Settings → Secrets and variables →
    Actions). Satır başına bir `grep -E` deseni, ör. `ornek-alan-adi\.com`.
  - Yerel: git'e girmeyen `.leak-deny` dosyası (aynı biçim).
- gitleaks secret taraması: CI'da her zaman, yerelde `GITLEAKS_DOCKER=1` ile.

Bulgu varsa log yalnızca dosya ve satır numarasını gösterir, eşleşen içeriği
göstermez. Gerçek bir secret bulunursa önce **iptal edip yenileyin**, sonra
dosyadan kaldırın. Yanlış alarmlar için ilgili satıra `# gitleaks:allow`
yorumu eklenebilir.

## Yerel notlar

`.claude/` altındaki ilerleme notları (`CLAUDE.md` hariç) ve
`ops/LIVE-REVIEW-*.md` gibi canlı ortam incelemeleri `.gitignore` ile repo
dışında tutulur. Canlı sisteme özel gözlemleri bu dosyalara yazın.
