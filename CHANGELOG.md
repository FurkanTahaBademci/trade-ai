# Değişiklik Günlüğü

Bu projedeki önemli değişiklikler bu dosyada tutulur. Biçim
[Keep a Changelog](https://keepachangelog.com/tr-TR/1.1.0/) yapısını, sürüm
numaraları [Semantic Versioning](https://semver.org/lang/tr/) kurallarını izler.

Yeni değişiklikleri `[Unreleased]` başlığının altına yazın; `make release`
bu bölümü yeni sürüm numarasıyla kapatır.

## [Unreleased]

## [0.8.2] - 2026-10-17

### Değişti

- **Web birden fazla süreçle çalışır.** Next.js sunucusu artık `WEB_WORKERS`
  (varsayılan 2, `auto` = CPU sayısı) kadar Node süreciyle aynı portu paylaşır;
  sayfa render'ı tek çekirdeğe sıkışmaz. Varsayılan `WEB_MEMORY_LIMIT` 512M'den
  1G'ye çıktı. `/health` çalışan süreç sayısını (`workers`) döndürür. Yönetim
  girişindeki kaba kuvvet sınırları süreçlere bölünür; toplam deneme hakkı
  değişmez.

## [0.8.1] - 2026-10-17

### Değişti

- **Canlı kapasite.**
  - API artık birden fazla uvicorn süreciyle çalışır (`API_WORKERS`,
    varsayılan 2). Migration'lar süreçler açılmadan önce bir kez çalışır.
  - Veritabanı bağlantı havuzu ayarlanabilir (`DB_POOL_SIZE`,
    `DB_MAX_OVERFLOW`); toplam bağlantı hesabı `docs/CONFIGURATION.md`'de.
  - Sık değişmeyen sayfa verileri (sinyal listeleri, ısı haritası, haber ve
    KAP akışlarının ilk sayfası, fon akımı, makro, portföy, karşılaştırma)
    web sunucusunda 30 sn-10 dk önbelleklenir. Yönetim sayfaları ve
    backtest listesi önbelleksizdir.
  - Kenar menüsü bağlantıları yalnız fareyle üzerine gelince ön yükleme
    yapar. Sayfa içi listeler ve filtreler ön yükleme yapmaz; her sayfa
    açılışı artık arka planda 15-20 ek sunucu isteği üretmez.
  - Haber, KAP ve AI analiz listeleri yanıtta olmayan büyük alanları (KAP
    gövdesi ve ekleri, ham RSS/KAP JSON'u, analiz kaynak metni ve ham model
    yanıtı) veritabanından okumaz.

## [0.8.0] - 2026-10-17

### Düzeltildi

- **Banka ve sigorta temel analizi.**
  - Finansal kurum tabloları (UFRS / UFRS_K) sanayi kalem kodlarıyla
    okunuyordu. Bankada özsermaye `2O`'dur, `2N` ise satış amaçlı varlık
    borcudur (0). Bu yüzden bankalarda PD/DD ve ROE boş, temel skor yanlıştı.
  - Bankada özsermaye, net faiz geliri, net kâr ve aktif toplamı okunur.
    Sigortada gelir okunmaz.
  - Finansallarda skor büyüme, özsermaye kârlılığı ve (bankada)
    özsermaye/aktif oranından hesaplanır.
  - `a3f9d2c7e1b4` migration'ı veri silmez. Bu hisseleri bir sonraki temel
    analiz partisinde yeniden çekime alır.
- **Hisse evreni.** İşlem görmeyen İş Bankası A, B ve kurucu payları (ISATR,
  ISBTR, ISKUR) ile KAP test üyesi (KTEST) artık skorlanmaz ve listelenmez.
- **KAP.**
  - Bildirim metnindeki `oda_*|` ve `[]` şablon artıkları hem kayıt sırasında
    hem okuma anında temizlenir.
  - Detay sayfası etiket–değer çiftlerini tanım listesi olarak gösterir.
  - KAP test bildirimleri kaydedilmez, listelenmez ve LLM'e gönderilmez.
- **Genel Bakış.**
  - AI gündem özeti son 24 saatin en yüksek etkili değerlendirmesini seçer.
    Eşik altındaysa kart gösterilmez.
  - Sabah bülteni haberleri etki ve güncelliğe göre seçer. Olay türleri
    Türkçedir.
- **Karşılaştırma.**
  - F/K, PD/DD, ROE ve net marj aynı son 12 ay temelinde hesaplanır.
  - Zarar eden şirkette F/K gösterilmez.
  - Oranlar Türkçe biçimdedir.
- **Hisse sayfası.** "Şirket haberleri" artık tüm ilgili haberleri listeler.
  Aynı belgenin tekrarlanan AI değerlendirmeleri tekilleştirildi.

### Değişti

- **Genel Bakış.** Üst satırda BIST100 ve piyasa genişliği gösterilir. En çok
  yükselen ve düşen hisseler eklendi.
- **Hisse sayfası.**
  - Bölüm çubuğu yapışkandır.
  - Analist hedeflerinin yaşı gösterilir.
  - Finansal kartların alt yüzdeleri etiketlidir.
  - Grafik kontrolleri sadeleşti. Tam ekran mobilde de vardır.
- **Piyasalar ve Hisse Tarayıcı.**
  - Sıralama iki yönlüdür. Görünüm ve sıralama adres çubuğunda tutulur.
  - Tablo başlıkları yapışkandır.
  - Mobilde kompakt liste, daraltılabilir filtreler ve özet ısı haritası
    gösterilir.
- **Araştırma sayfaları.**
  - Sinyaller listesi analiz bölümlerini aşağı itmez.
  - Takvimde "Bugün" işareti var.
  - AI analizlerinde minimum etki filtresi var (`GET /api/evaluations?min_impact=`).
  - Analiz detayındaki teknik alanlar yalnız yöneticiye görünür.
  - Portföy tavanı aşan pozisyonu uyarı rengiyle gösterir.
  - Detay sayfalarının sekme başlıkları içerik başlığıdır.
- **Menü ve arama.** Girişli sayfalarda kilit simgesi var. Global arama
  sayfaları da bulur.
- **Biçim ve erişilebilirlik.**
  - Yüzdeler Türkçe "%41,5" biçimindedir.
  - Bin kısaltması "Bin" olarak yazılır.
  - Odak halkası görünürdür.

## [0.7.0] - 2026-10-17

### Eklendi

- **Backtest: sıralama sepeti stratejisi.**
  - Her N işlem gününde, o günden önceki son skorlara göre skoru en yüksek
    hisseler eşit ağırlıkla tutulur. Sepet boyutu, elde tutma sırası ve
    dengeleme aralığı ayarlanabilir.
  - Tavan/taban ve likidite kuralları geçerli. Engellenen alım ve satışlar
    sonraki işlem günlerinde yeniden denenir.
- **Backtest: ağırlık simülasyonu.** Skor, saklanan bileşen skorlarından
  seçilen ağırlıklarla yeniden hesaplanır. Böylece model değişmeden önce
  farklı ağırlıklar geçmişte denenebilir.
- **Backtest: başlangıç günü hassasiyeti.**
  - Her koşu, başlangıcı 2, 4, 6 ve 8 işlem günü kaydırılmış dört ek koşuyla
    tekrarlanır. XU100'e göre ortalama, en kötü ve en iyi fark raporlanır.
  - 6 aylık veride yalnız bu kayma, aynı stratejinin sonucunu +7 ile −8 puan
    arasında oynattı.
  - Yeni `backtest_run.robustness` alanı eklendi (`e5a7c3d9b1f4` migration'ı).
- Backtest sonucunda **ortalama yatırım oranı**: sermayenin ortalama ne kadarının
  hisselerde olduğu. Düşük oran, sonucun büyük kısmının nakitte beklemekten
  geldiğini gösterir.
- **Bileşik Sinyaller: ağırlık senaryoları tablosu.** Canlı model, "analist
  %10", "analist yok", "temel + momentum ağırlıklı" ve "eşit ağırlık"
  senaryolarının hisseleri sıralama gücü (IC) aynı geçmişte, her rapor
  yenilemesinde hesaplanır. Yeni uç: `GET /api/signals/weight-scenarios`.
- Bileşik skor kaydı artık bileşen güvenlerini de saklar
  (`evidence.confidences`). Ağırlık simülasyonu bunları kullanır.

### Değişti

- **Paper portföy `paper-v5`: çıkış eşiği 40 yerine 55.**
  - 6 aylık walk-forward'da eğitim döneminin en iyi beş kombinasyonunun hepsi
    55 kullandı.
  - 10 farklı başlangıçta XU100'e göre ortalama fark −10,6 yerine −8,6 puan
    oldu.
  - Geçişte skoru 55'in altında olan açık pozisyonlar sonraki koşuda satılır.
- Backtest `backtest-v4`.
  - Varsayılan çıkış skoru 55.
  - Sinyaller kanıt (evidence) JSON'unun tamamı olmadan okunur.
  - Form, strateji ve ağırlık gruplarına ayrıldı.
  - Sayfa başlığı sabit `backtest-v1` yerine koşunun sürümünü gösterir.

### Düzeltildi

- Hisse Tarayıcı (`/tarayici`), sonuç olan her aramada "server error"
  veriyordu. Sunucu bileşeni, "use client" modülündeki yardımcı fonksiyonu
  çağırıyordu. Bu tür hatayı derleme yakalamadığı için yeni bir web testi
  (`client-boundary`) eklendi.

## [0.6.0] - 2026-10-17

### Değişti

- **Daha az veritabanı yükü (okuma tarafı).**
  - Sistem sayaçları (haber, KAP, AI analizi toplamları ve kırılımları) büyük
    tablolarda `count(*)` ile tüm tabloyu taramak yerine PostgreSQL planlayıcı
    istatistiğinden tahmin edilir; 100 binden küçük tablolarda kesin sayım
    sürer. Sayaçlar 5 dakika önbelleklenir. "Takip edilen fon" tüm geçmişte
    `DISTINCT` yerine son günün fonlarını sayar.
  - Isı haritası son skoru bulmak için tüm skor geçmişini taramaz; yalnız son
    skor günü okunur.
  - Akıllı haber sıralaması yalnız son 30 günü puanlar; değerlendirme seçimi
    pencere fonksiyonu yerine `DISTINCT ON` ile yapılır.
  - Karşılaştırma, hisse başına ayrı sorgu yerine iki toplu sorgu kullanır;
    sabah bülteni skorların yalnız gereken kolonlarını okur.
  - AI analizleri listesi ve günlük LLM token bütçesi kontrolü için yeni
    indeksler (`d4b8e2f1a6c3` migration'ı).
- **Daha az veritabanı yükü (yazma tarafı, arka plan işleri).**
  - LLM değerlendirmesi (10 dakikada bir) belgeleri yalnız gereken kolonlarla
    okur; daha önce değerlendirilmiş belgeleri belge başına sorgu yerine tek
    sorguda eler. Durgun bir koşu ~580 yerine ~80 SQL ifadesi çalıştırır.
  - KAP, haber, temel analiz, analist ve hisse listesi toplayıcıları satır satır
    yerine çok satırlı toplu upsert kullanır. KAP ve haberde içeriği değişmeyen
    satırlar her koşuda yeniden yazılmaz (ölü satır ve WAL üretmez);
    `updated_at` yalnız içerik değişince güncellenir.
  - KAP koşusu detay kontrolü için büyük detay JSON'unu çekmez; bildirimler,
    fon akımı, paper portföy ve analist konsensüsü yalnız ihtiyaç duyduğu
    kolonları ve tarih aralığını okur.
  - Fiyat toplayıcısı ilk kurulum kontrolü için tüm fiyat tablosunu saymaz;
    kısa geçmişli hisse tespiti `GROUP BY` yerine indeksli `NOT EXISTS` kullanır.
- LLM backlog'u ve yeniden denemeler son 30 günle sınırlandı: model/prompt
  değişince tüm geçmiş yeniden değerlendirilip ücretlendirilmez (sinyaller
  zaten yalnız son 14 günü kullanır).
- Analist konsensüsündeki piyasa fiyatı son 30 günün kapanışından alınır.
- **Hisse sayfası akışla yüklenir.** İlk ekran için 8 istek beklenir (önceden
  13 + 2 sıralı); haber/KAP, AI/portföy ve faiz bölümleri hazır oldukça gelir.
  Fiyat geçmişi grafiğe nesne yerine kompakt diziler olarak gönderilir (aynı
  veri JSON'da yarıdan az yer tutar).
- Hisse Tarayıcı tablosu ve Piyasalar listesi istemciye yalnız gösterilen
  alanları gönderir.

### Düzeltildi

- Akıllı haber akışında aşağı kaydırırken haberler tekrar ediyor veya
  atlanıyordu: sıralama her sayfada "şimdi"ye göre yeniden hesaplanıyordu.
  Artık tüm sayfalar ilk sayfanın zamanıyla sıralanır (`ref` parametresi).
- Bileşik sinyal listesinde gece yarısı yeni skor günü oluşursa sonraki
  sayfalar başka günden geliyordu; imleç artık skor tarihini taşır.
- KAP listesinde index'i veya tarihi bozuk tek bir satır tüm toplama koşusunu
  durduruyordu; artık o satır loglanıp atlanır ve sonuçta `list_failures`
  olarak raporlanır.

## [0.5.1] - 2026-10-16

### Düzeltildi

- Canlıda çoğu hissenin fiyat geçmişi yalnız birkaç haftaydı (ör. THYAO, GARAN
  4 Eylül 2026'dan başlıyordu; ASELS'te 3 yıl vardı). İlk kurulumdaki fiyat
  doldurması yarıda kalmış, toplayıcı ise yeniden doldurma kararını tablodaki
  toplam satır sayısına göre verdiği için bir daha denememişti. Grafikler, skor
  geçmişindeki momentum bileşeni ve backtest bundan etkileniyordu. Fiyat işi
  artık ilk fiyatı 2 yıldan yeni olan aktif hisselerin 3 yıllık geçmişini
  doldurur (kaynakta da kısa geçmişi olan yeni halka arzlar 30 günde bir
  denenir) ve ardından skor geçmişini otomatik olarak yeniden hesaplatır.

## [0.5.0] - 2026-10-16

### Eklendi

- Backtest'te isteğe bağlı rejim filtresi (XU100 N günlük ortalamasının
  altındayken yeni pozisyon açılmaz) ve oynaklık sınırı (son 20 işlem günü
  günlük getiri oynaklığı eşiği aşan hisseye girilmez). İkisi de varsayılan
  olarak kapalıdır; geçmiş testlerde etkileri döneme göre değişti.

### Değişti

- **Gerçekçi yürütme (paper `paper-v4`, backtest `backtest-v3`).** BIST'te
  tavanda kapanan hisse o kapanıştan alınamaz, tabanda kapanan satılamaz.
  Artık günü %9,5 ve üzeri yükselişle kapatan hisseye girilmez; aynı oranda
  düşüşle kapatan pozisyonun satışı (zarar-kes dahil) ertesi işlem gününe
  kalır. Son 20 işlem günü ortalama hacmi 20 milyon TL'nin altındaki
  hisselere yeni pozisyon açılmaz. Eylül–Ekim 2026 canlı skorlarıyla eski
  varsayım (her kapanıştan işlem) mevcut stratejiyi -%8,2 gösterirken
  gerçekçi kurallarla sonuç -%13,3'tür (XU100 -%15,2): tabana kilitlenen
  bir hissede zarar-kes 23 Eylül'de ₺337'den değil, 12 Ekim'de ₺96'dan
  gerçekleşebildi. Eşikler backtest formundan değiştirilebilir.
- Backtest, günlük değişim ve ortalama hacim için başlangıçtan önceki 45
  günün fiyatlarını kullanır; sermaye eğrisi yine seçilen başlangıç gününden
  başlar.

## [0.4.1] - 2026-10-16

### Düzeltildi

- BIST100 (XU100) endeks geçmişi kurulum gününden önceye gitmiyordu: zamanlanmış
  iş yalnız son 5 günü çekiyordu. Endeks hem işlem günü takvimi hem momentum
  bileşeni için kullanıldığından skor geçmişi, momentum, sinyal doğruluğu,
  bileşen gücü ve backtest yalnız kurulumdan sonraki birkaç haftayı
  görebiliyordu. Endeks tablosunda 400'den az gün varsa toplayıcı bir kez
  3 yıllık geçmişi çeker. Endeks olmadan (momentumsuz) hesaplanmış skor
  günleri, worker'ın geçmiş doldurma adımında otomatik olarak yeniden
  hesaplanır; son 180 günün tamamı birkaç saat içinde dolar.

## [0.4.0] - 2026-10-15

### Eklendi

- **Bileşenlerin tahmin gücü:** `/sinyaller` sayfasında AI etkisi, temel
  analiz, analist görüşü, momentum ve bileşik skorun sonraki 5/10/20 işlem
  günü getirisini ne kadar doğru sıraladığı: günlük sıra korelasyonu (IC)
  ortalaması, IC'nin pozitif olduğu günlerin oranı ve üst/alt beşlik getiri
  farkı. Yeni uç nokta: `GET /api/signals/component-power`.
- Hisse sayfasında günlük değişim, 52 haftalık fiyat aralığı ve şirket
  takvimi (yaklaşan genel kurul, temettü, sermaye artırımı, finansal rapor ve
  son 45 günün olayları).
- KAP, haber ve AI analizi listelerinde hisse filtresi (`?hisse=THYAO`);
  hisse sayfasındaki ilgili bölümlerde "Tümünü gör" bağlantıları.
- İzleme listesinde son fiyat ve günlük değişim sütunları (CSV dahil).
- Backtest'te zarar-kes ve günlük yeni pozisyon sınırı. Varsayılanlar paper
  portföyle aynıdır (%15, günde 3); 0 kuralı kapatır. Strateji sürümü
  `backtest-v2`; eski koşular değişmez.

### Değişti

- Sinyal doğruluğu ve bileşen gücü raporları kullanıcı isteğinde değil,
  worker'da önceden hesaplanır. `/sinyaller` sayfası soğuk önbellekte 6–10 sn
  bekleyip doğruluk tablosunda hata gösterebiliyordu.
- Sinyal doğruluğu, aynı hisse için aynı giriş kapanışına düşen sinyallerden
  (cuma, cumartesi ve pazar skorları pazartesi kapanışından girer) yalnız en
  güncelini sayar; hafta sonları aynı gözlem üç kez sayılıyordu. Gözlem
  sayıları bu nedenle azalır.
- Bileşik skordaki AI bileşeni, tazeliği haberin/bildirimin yayın zamanına
  göre ölçer. Kota beklemesinden veya model değişikliğinden sonra yeniden
  değerlendirilen eski bir haber artık "bugünün haberi" sayılmaz; 15 günden
  eski kaynaklar hiç sayılmaz.
- Hisse Tarayıcı 200 yerine 100 satırla açılır; "Daha fazla göster" ile
  100'er satır eklenir. Varsayılan sayfa (canlıda ~545 KB) bu sayede
  hafifler.
- Piyasa özeti (arama paleti, izleme listesi) skoru tüm evren için tarayıcı
  veri setinden alır ve 60 sn önbelleğe alınır. Önceden en yüksek 500 skor
  dışında kalan hisseler "Sinyal yok" görünüyordu.
- Takvimde aynı şirketin aynı gün yayımladığı finansal rapor paketi
  (Finansal Rapor, Faaliyet Raporu, Sorumluluk Beyanı) tek olay olarak
  gösterilir.
- Sabah bülteninde politika faizi Türkçe sayı biçimiyle yazılır
  (`%37.00` yerine `%37`).

### Düzeltildi

- Fiyat ve TEFAS toplayıcılarında TLS sertifika doğrulaması kapalıydı
  (`verify=False`); açıldı. Fiyat isteği hata verirse bir kez yeniden
  denenir; hisselerin %10'undan fazlası alınamazsa Sistem Sağlığı'nda kısmi
  hata görünür (önceden hatalar sessizce yutuluyordu).
- İzleme listesinde hızlı ardışık yıldızlamada sunucuya giden istekler
  sırasız varıp bir hisseyi listeden düşürebiliyordu; yazmalar sıraya alınır.
- Hisse Tarayıcı'da skor etiketi iki satıra kırılıyordu.

### Not

- v0.3.0 yükseltme notundaki `run_once tcmb-policy --refresh` komutu
  gerekli değildir: canlıdaki TCMB kararları eksik değildi, eksiklik tespiti
  sayfa metni çıkarılırken yapılan bir hatadan kaynaklanıyordu.

## [0.3.0] - 2026-10-14

### Eklendi

- **Sürüm gösterimi:** sol menünün en altında çalışan sürüm (`v0.3.0`) ve
  biliniyorsa kısa commit. Web ve API `/health` yanıtları `version` ve
  `commit` döndürür; `/sistem` web ile API farklı sürümdeyse uyarır. Yeni
  sürüm yayınlandığında açık sekmeler ilk gezinmede tamamen yenilenir.
- Yayın iş akışı, `COOLIFY_DEPLOY_WEBHOOK` ve `COOLIFY_API_TOKEN` repo
  secret'ları tanımlıysa testlerden geçen sürümü Coolify'da canlıya alır.
  Auto Deploy kapatılarak canlıya yalnız etiketli sürümler çıkarılabilir
  (bkz. `docs/RELEASING.md`).
- Docker imajlarında derlenen commit (`SOURCE_COMMIT` build argümanı) ve OCI
  etiketleri.
- **Hisse Tarayıcı (`/tarayici`):** tüm BIST evrenini bileşik skor, sinyal,
  sektör, piyasa değeri, F/K (son 12 ay), PD/DD, ROE, gelir büyümesi, 1 aylık
  getiri ve analist potansiyeline göre filtreleme; sütunlara göre sıralama,
  hazır taramalar ("Ucuz ve güçlü skor", "Analist favorileri", "Momentum
  liderleri", "Kârlı büyüme", "Büyük şirketler") ve CSV. Filtreler adres
  çubuğunda tutulur, taramalar paylaşılabilir. Yeni uç noktalar:
  `GET /api/markets/screener` ve `GET /api/markets/screener.csv`.
- **Günlük özet bildirimi:** işlem günü sonunda Telegram/webhook'a BIST100,
  paper portföy, günün işlemleri, skoru en çok değişen ve en yüksek skorlu
  hisseler. `/sistem` → Ayarlar → "Günlük Özet Bildirimi" ile açılır
  (varsayılan kapalı); takvimde "Günlük özet bildirimi" işi olarak görünür.
- **Skor hareketleri:** `/sinyaller` sayfasında son gün, hafta veya ayda
  bileşik skoru en çok yükselen ve düşen hisseler (etiket değişimiyle).
  Yeni uç nokta: `GET /api/signals/movers?days=7&limit=10`.
- Hisse sayfasında F/K ve PD/DD. F/K son 12 ay (TTM) net kârıyla hesaplanır;
  `GET /api/fundamentals/{ticker}` yanıtına `ttm_net_income` ve `ttm_basis`
  alanları eklendi.
- Sinyaller sayfasında Negatif ve Çok negatif filtreleri.
- Haber ve KAP detayında ilgili AI değerlendirmesine, AI analiz detayında
  kaynak habere/bildirime bağlantı.
- Paper portföy sayfasında gerçekleşen K/Z ve satış işlemlerinin K/Z'si.
- Sistem Sağlığı'nda "Devre dışı" durumu: yapılandırma eksikliği nedeniyle
  hiç veri toplamayan toplayıcı (örneğin `EVDS_API_KEY` tanımlı değilken
  EVDS) artık "Sağlıklı" görünmez.

### Değişti

- **Paper portföy `paper-v3`.** İşlemler yalnız işlem günlerinde (XU100
  takvimi) ve sinyal gününden sonraki kapanışta yapılır; backtest ile aynı
  kural. v2 aynı günün kapanışında, kapanıştan sonra gelen haberlerle
  hesaplanmış skorla ve hafta sonları da (cuma kapanışından) işlem yapıyordu.
  Kaçırılan işlem günleri (en fazla 5) sırayla telafi edilir. Geçmiş işlemler
  değişmez.
- v3 skor geçmişi elle komut beklemeden doldurulur: worker her sinyal
  koşusunda son 180 günün eksik günlerinden 5'ini hesaplar. Sinyal doğruluğu
  tablosu ve backtest yükseltmeden birkaç saat sonra dolar.
- Geçmiş bir gün için skor hesaplanırken finansal tablo, SPK ilan süresi
  (güvenlik payıyla) dolmuşsa o gün biliniyor kabul edilir. Önceden haftalık
  yenileme zaman damgasını güncellediği için geriye dönük skorlarda temel
  analiz bileşeni neredeyse hiç yoktu. Bugünün skoru değişmez.
- Backtest ve sinyal doğruluğu hesapları API'nin olay döngüsünü bloklamaz;
  uzun bir backtest sırasında diğer sayfalar yanıt vermeye devam eder.
  Backtest motorundaki doğrusal olmayan tarama kaldırıldı.
- Sinyal motoru her koşuda LLM değerlendirmelerinin büyük metin kolonlarını
  ve tüm fiyat geçmişini okumaz.

### Düzeltildi

- Hisse sayfasında finansal oranlar (gelir/kâr büyümesi, marjlar, özsermaye
  kârlılığı) 100 kat küçük gösteriliyordu (+%40 yerine +0,4%).
- Karşılaştırmada F/K, yıl içi kümülatif dönem kârıyla hesaplandığı için
  ara dönemlerde 2–4 kat büyük çıkıyordu.
- Paper portföyde zarar-kes/kâr-al ile satılan hissenin skoru hâlâ yüksekse
  aynı koşuda yeniden alınmaya çalışılıyor, koşu benzersizlik hatasıyla
  tamamen geri alınıyordu (satış dahil).
- Paper portföy aynı gün ikinci kez çalıştırıldığında ("Şimdi çalıştır")
  günlük 3 yeni pozisyon sınırı yeniden açılıyordu.
- Karşılaştırma sayfasında hisse eklemek/çıkarmak veya hazır grup seçmek
  URL'yi değiştiriyor ama ekrandaki karşılaştırma güncellenmiyordu.
- TCMB faiz kararı toplayıcısında tek bir karar sayfasının hatası tüm koşuyu
  düşürüyordu; artık kısmi hata olarak raporlanır, diğer kararlar kaydedilir.
- Hisse sayfası API'ye ulaşamadığında "Şirket bilgisi yükleniyor" yerine
  hizmet uyarısı gösterir.
- Ana sayfada bileşik skor listesinin alt başlığı ("Güncel teknik görünüm").

### Yükseltme notu

- Canlı ortamda eksik görünen TCMB kararları için bir kez:
  `docker compose exec api python -m scripts.run_once tcmb-policy --refresh`.
- Mevcut paper portföy bir sonraki işlem gününden itibaren `paper-v3`
  kuralıyla devam eder; ek işlem gerekmez.

## [0.2.0] - 2026-10-10

### Eklendi

- `/makro` sayfasında TCMB EVDS'den USD/TRY, EUR/TRY gösterge kurları ve TÜFE
  (yıllık değişimle). Yeni isteğe bağlı ayar: `EVDS_API_KEY`; tanımlı değilse
  toplayıcı çalışmaz ve kartlar görünmez.
- İzleme listesi yönetici girişliyken sunucuya senkronlanır ve Telegram/webhook
  bildirimleri bu listedeki hisselerin etiket değişimlerini de izler.
  Ziyaretçilerde liste yalnız tarayıcıda kalır.
- Piyasalar hisse listesinde son fiyat, günlük değişim, işlem hacmi, sektör ve
  bileşik skor sütunları; değişim, hacim veya skora göre sıralama. Skoru
  olmayan hisseler "50 / Nötr" yerine "—" gösterir.
- Takvimde genel kurullar toplantı gününe, temettüler hak kullanım (paysuz
  işlem) gününe yerleşir; ödeme tarihi detayda gösterilir. Tarihler KAP form
  metninden toplama sırasında çıkarılır. Eski bildirimler için:
  `python -m scripts.run_once kap-event-dates`.
- Yönetim ekranları için `/giris` giriş sayfası: imzalı ve 12 saat geçerli
  oturum çerezi, `/sistem` ve `/backtest` başlıklarında "Çıkış yap" düğmesi,
  hatalı denemelere karşı kilit. Giriş sonrası açılmak istenen sayfaya dönülür.

### Değişti

- Tarayıcının HTTP Basic Auth penceresi kaldırıldı. Mevcut
  `WEB_ADMIN_USERNAME` / `WEB_ADMIN_PASSWORD` ayarları aynen kullanılır; yeni
  ayar gerekmez. Parola değiştirildiğinde tüm açık oturumlar kapanır.
- Paper portföy işlem gerekçeleri Türkçe ve okunur biçimde yazılır
  ("Bileşik skor 87,5 ≥ 75; güven %35"). Eski işlemler değişmez.
- **Bileşik skor modeli v3.** v1 geçmişi veritabanında kalır; ekranlar,
  paper portföy, backtest ve bildirimler v3'ü kullanır. Ağırlıklar: AI etkisi
  %35, temel analiz %28, analist %22, momentum %15.
  - Yeni momentum bileşeni: hissenin XU100'e göre 20 ve 60 işlem günlük göreli
    getirisi (±%25 göreli performans 0–100 bandına eşlenir).
  - TEFAS fon akımı skordan çıkarıldı: piyasa geneli tek bir sayı olduğu için
    her hisseye aynı puanı (47) veriyor ve yalnız analist verisi olan hisseleri
    "iki bileşenli" gösteriyordu.
  - Analist konsensüsü 180 günden eski tavsiyeleri saymaz, kalanları 90 günlük
    yarı ömürle ağırlıklandırır; ortalama tavsiye yaşı arttıkça güven düşer.
  - Güveni %60'ın altındaki skorlar nötre (50) doğru orantılı çekilir; ham
    skor `evidence.raw_score` alanında saklanır.
  - Geçmiş bir tarih için hesaplanan skor o tarihte bilinmeyen veriyi kullanmaz.
- Sinyal doğruluğu tablosu BIST100'e göre fazla getiriyi ve endeksi yenme
  oranını gösterir; mutlak getiri ikinci satıra taşındı.
- `run_once signals --days N` ile v3 skor geçmişi geriye dönük doldurulabilir.
- Paper portföy risk varsayılanları: zarar-kes %15, sektör limiti %30,
  yeniden dengeleme açık (kâr-al ve takip eden stop kapalı). `/sistem`
  ekranında kaydedilmiş değerler geçerliliğini korur.
- Paper portföy aynı gün en fazla 3 yeni pozisyon açar; tek bir haberin
  portföyün büyük bölümünü aynı gün doldurması engellenir. Strateji sürümü
  `paper-v2`.
- Paper portföy sayfasında BIST100'e göre fazla getiri kartı.
- Piyasa dışı haberler (spor, kültür-sanat, hava durumu, asayiş) kural
  tabanlı bir ön filtreyle Gemini'ye gönderilmeden `filtered` olarak
  işaretlenir. Ticker veya ekonomi terimi içeren her haber yine
  değerlendirilir. AI Analizleri listesi ve sayaçlar bu kayıtları göstermez.

### Yükseltme notu

Migration'lardan sonra v3 geçmişini bir kez doldurun:
`docker compose exec api python -m scripts.run_once signals --days 180`.
Doldurulmadan backtest ve doğruluk tablosu yalnız yeni günleri görür.

### Düzeltildi

- Şirket karşılaştırmasında konsensüs getiri potansiyeli 100 kat büyük
  gösteriliyordu (+6.454% yerine +64,5%).
- Dünya ve Foreks haberlerinde `&#039;` gibi çözülmemiş HTML kodları
  görünüyordu; toplayıcı düzeltildi, mevcut kayıtlar migration ile temizlenir.
- Veri kaynağı ve zamanlama etiketlerindeki eksik Türkçe karakterler.
- Karşılaştırma tablosunda fiyat ve skorlar Türkçe sayı biçimiyle gösterilir.
- `robots.txt` ve site simgesi eklendi (önceden 404).
- Temel analiz toplayıcısı gündemdeki hisseleri alfabetik sıralayıp ilk 50'yi
  aldığı için THYAO, PGSUS gibi alfabenin sonundaki hisseler hiç
  işlenmiyordu. Artık tüm evren günlük 120'lik partilerle dönüşümlü
  güncellenir (önce hiç çekilmemişler, 7 günde bir yenileme).
- Hisse evreninde payları borsada işlem görmeyen şirketler ve borçlanma aracı
  ihraççı kodları (ACP, ALK, TGB gibi) artık pasif; sinyal ve sayaçlara
  girmez.
- Bileşik Sinyaller sayfası soğuk önbellekte ~20 sn bekleyip doğruluk
  tablosu yerine hata gösteriyordu: doğruluk sorgusu yalnız sinyal dönemindeki
  fiyatları çeker, web istemcisi zaman aşımında yeniden denemez.
- Takvim sorgusu KAP gövde metni ve eklerini yüklemeden yalnız gereken
  kolonları okur.
- Kök layout `force-dynamic` olduğu için web tarafındaki `revalidate`
  ayarları etkisizdi; `apiGet` artık bu istekleri süreç içinde kısa süre
  önbelleğe alır (yalnız başarılı yanıtlar).

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
