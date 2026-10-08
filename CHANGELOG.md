# Değişiklik Günlüğü

Bu projedeki önemli değişiklikler bu dosyada tutulur. Biçim
[Keep a Changelog](https://keepachangelog.com/tr-TR/1.1.0/) yapısını, sürüm
numaraları [Semantic Versioning](https://semver.org/lang/tr/) kurallarını izler.

Yeni değişiklikleri `[Unreleased]` başlığının altına yazın; `make release`
bu bölümü yeni sürüm numarasıyla kapatır.

## [Unreleased]

### Eklendi

- Yönetim ekranları için `/giris` giriş sayfası: imzalı ve 12 saat geçerli
  oturum çerezi, `/sistem` ve `/backtest` başlıklarında "Çıkış yap" düğmesi,
  hatalı denemelere karşı kilit. Giriş sonrası açılmak istenen sayfaya dönülür.

### Değişti

- Tarayıcının HTTP Basic Auth penceresi kaldırıldı. Mevcut
  `WEB_ADMIN_USERNAME` / `WEB_ADMIN_PASSWORD` ayarları aynen kullanılır; yeni
  ayar gerekmez. Parola değiştirildiğinde tüm açık oturumlar kapanır.

## [0.1.0] - 2026-10-08

İlk açık kaynak sürüm.

### Eklendi

- KAP bildirimleri, ekonomi haberleri (RSS), temel analiz, analist hedef
  fiyatları, kurum raporları, TEFAS fon akımları, BIST100 endeksi ve TCMB para
  politikası kararları için idempotent veri toplayıcıları.
- Gemini ile iki katmanlı (Tier 1 / Tier 2) haber ve KAP değerlendirmesi;
  varsayılan olarak kapalı, günlük token bütçesi ve maliyet korumalı.
- Hisse başına sürümlü 0–100 bileşik sinyal skoru, sinyal geçmişi ve isabet
  ölçümü.
- Komisyon, kayma ve risk kurallarıyla (stop-loss, take-profit, takip eden stop,
  pozisyon/sektör ağırlık sınırları) çalışan paper portföy motoru. Canlı emir
  iletimi yoktur.
- Sinyal stratejisi için backtest motoru ve BIST100 karşılaştırması.
- Next.js dashboard: piyasalar, sinyaller, haberler, KAP, AI analizleri,
  kurumsal görüş, makro, piyasa takvimi, karşılaştırma, izleme listesi,
  portföy, backtest ve sistem yönetimi ekranları; CSV dışa aktarma.
- `/sistem` ekranından tarama takvimi, çalışma zamanı ayarları, Gemini bağlantı
  testi, Telegram/webhook bildirimleri ve veri kalitesi izleme.
- Docker Compose / Coolify dağıtımı, sağlık kontrolleri, yedekleme/geri yükleme
  ve production ön kontrol betikleri.
- Yönetim ekranları için HTTP Basic Auth ve backend yazma uçları için yönetim
  anahtarı; `make init` ile güçlü parolaların otomatik üretilmesi.
