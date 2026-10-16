import type { Price } from "./types";

/**
 * Grafiğe giden fiyat satırı: [tarih, kapanış, yüksek, düşük, ortalama, TL hacim].
 * Nesne yerine dizi göndermek yıllık geçmişte her satırda tekrar eden alan
 * adlarını ve grafiğin kullanmadığı kolonları (USD kapanış, piyasa değeri) sayfa
 * yükünden çıkarır.
 */
export type CompactPrice = [string, number, number | null, number | null, number | null, number | null];

export function compactPrices(prices: Price[]): CompactPrice[] {
  return prices.map((row) => [row.date, row.close, row.high, row.low, row.avg_price, row.volume_try]);
}

export function expandPrices(rows: CompactPrice[]): Price[] {
  return rows.map(([date, close, high, low, avg_price, volume_try]) => ({ date, close, high, low, avg_price, volume_try, close_usd: null, market_cap_try: null }));
}
