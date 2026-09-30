# Canli sistem incelemesi — 2026-09-30

Hedef: `https://trade.furkantahabademci.com.tr/`
Gozlem araligi: yaklasik 13:16–13:27 Europe/Istanbul. Canli sistemde veri
degistiren islem yapilmadi; ayar, takvim, Gemini istegi ve backtest
tetiklenmedi.

## Canli durum

- Ana sayfa, sistem, backtest, haber, KAP ve THYAO detay sayfalari HTTP 200
  dondu. Web health yaniti `{"status":"ok","service":"web"}` idi.
- Sistem ekrani PostgreSQL ve Redis'i bagli, veri hatlarini 11/11 saglikli,
  sorun ve ilk calisma bekleyen sayilarini 0 gosterdi.
- AI hatti anlik olarak 500 basarili, 0 hatali, 8 bekleyen belge, 6.625
  cozulmemis hata ve 30 dakikadan uzun suredir calisiyor gorunen 7 kayit
  gosterdi. Son tamamlanma gozlem anindan yaklasik 9 dakika onceydi.
- Market feed 809 benzersiz ticker dondurdu. Bunlarin 500'unde guncel bilesik
  skor vardi; 309 ticker henuz skorsuzdu. Skorlu dagilim 419 `NEUTRAL`, 79
  `POSITIVE`, 2 `VERY_POSITIVE` idi.
- Sicak isteklerde olculen sayfa/API sureleri genellikle 0,10–1,51 saniye
  araligindaydi. `/sinyaller` bir soguk-cache isteginde 20,32 saniye surdu;
  sonraki uc istek 0,10–0,28 saniyede tamamlandi.
- HTTP, HTTPS'e 307 ile yonleniyor. TLS sertifikasi Google Trust Services
  tarafindan verilmis ve 6 Aralik 2026'ya kadar gecerli.

## Bulunan riskler ve yapilan gelistirmeler

1. **Kritik — yonetim yuzeyi public idi.** Canlida `/sistem` ve `/backtest`
   kimlik dogrulama olmadan aciliyordu. Server Action'lar backend admin
   anahtarini sunucu tarafinda kullandigi icin sayfayi bilen bir ziyaretci
   takvim/ayar/depolama bakimi ve backtest islemlerini tetikleyebilirdi.
   Next.js Proxy katmaninda HTTPS Basic Auth eklendi; ayni yetki her Server
   Action icinde tekrar kontrol ediliyor. Production, credential eksikse
   acik kalmak yerine 503 ile kapali kaliyor. Protected link prefetch'i,
   diger sayfalarda istemsiz parola penceresi acmamasi icin kapatildi.

2. **Yuksek — terk edilmis AI kayitlari kalici `running` gorunuyordu.** Worker
   her dongunun basinda 30 dakikayi asan guncel model kayitlarini denetlenebilir
   `failed` durumuna uzlastiriyor. Deneme hakki kalan kayitlar normal retry
   secimine tekrar girebiliyor; deneme limiti dolanlar artik sonsuza kadar
   calisiyor gibi raporlanmiyor.

3. **Orta — sinyal dogruluk soguk-cache hesabi pahaliydi.** Fiyat bulma
   algoritmasi tekrarli doğrusal taramadan ikili aramaya cevrildi. SQL sorgusu
   artik `component_scores`, `weights` ve `evidence` JSON alanlari yerine sadece
   gerekli dort kolonu okuyor. Cache 5 dakikadan 15 dakikaya cikarildi.

4. **Orta — HTTPS katilastirma basligi eksikti.** Tum web yanitlarina bir
   yillik `Strict-Transport-Security` basligi eklendi. Mevcut frame, MIME,
   referrer ve permission basliklari korunuyor.

5. **Operasyon — ayri web parolasi.** `WEB_ADMIN_USERNAME` ve
   `WEB_ADMIN_PASSWORD` Compose/env/preflight belgelerine eklendi. Gecis
   uyumlulugu icin parola bosken `ADMIN_API_TOKEN` kullanilir; ayri ve en az 16
   karakterli parola onerilir.

## Dogrulama

- Backend: 204 test gecti; Ruff temiz.
- Web: 47 test gecti; TypeScript temiz; Next.js 16.3.4 production build gecti.
- Yerel production HTTP testi: `/health` anonim 200; `/sistem` ve `/backtest`
  anonim 401 + `WWW-Authenticate`; dogru credential ile ikisi de 200.
- Sentetik production degiskenleriyle preflight tamamen gecti.
- Repository diff whitespace kontrolu temiz.

## Deploy notu

Bu inceleme kodu ve testleri hazirlar; Coolify'a deploy yapilmadi. Canli sistem,
yeni image yayinlanana kadar public yonetim yuzeyi ve eski AI/performance
davranisini surdurur. Deploy oncesi guclu `WEB_ADMIN_PASSWORD` tanimlanmali;
deploy sonrasi `make production-smoke`, anonim 401/dogru credential 200 ve
bir sonraki evaluation dongusunden sonra 30 dk+ `running` sayisinin sifirlanmasi
kontrol edilmelidir. 6.625 tarihsel hata otomatik silinmemistir; denetim izi
korunmustur.
