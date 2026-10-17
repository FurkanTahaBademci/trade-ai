// Genel Bakış (ana sayfa) için saf hesaplar: endeks özeti, piyasa genişliği,
// en çok yükselen/düşenler ve sinyal dağılımı. Bileşenden ayrı tutulur ki
// node:test ile doğrudan test edilebilsin.

export type IndexPoint = { date: string; value: number };
export type IndexSnapshot = { value: number; changePct: number | null; date: string };

/** Son kapanış ve bir önceki güne göre % değişim. Satırlar tarih sırasız gelebilir. */
export function indexSnapshot(rows: IndexPoint[]): IndexSnapshot | null {
  const valid = rows.filter((row) => Number.isFinite(row.value) && row.value > 0).sort((a, b) => a.date.localeCompare(b.date));
  const last = valid.at(-1);
  if (!last) return null;
  const prev = valid.at(-2);
  return { value: last.value, date: last.date, changePct: prev ? ((last.value - prev.value) / prev.value) * 100 : null };
}

export type MoverStock = { ticker: string; name: string; last_price: number; change_pct: number; volume_try: number };

// Sığ hisselerin tavan/taban hareketleri listeyi doldurmasın diye en az bu kadar
// günlük işlem hacmi (TRY) aranır; yeterli hisse yoksa eşik kaldırılır.
export const MOVER_MIN_VOLUME_TRY = 10_000_000;

export function marketMovers<T extends MoverStock>(stocks: T[], limit = 5, minVolume = MOVER_MIN_VOLUME_TRY): { gainers: T[]; losers: T[] } {
  const priced = stocks.filter((stock) => Number.isFinite(stock.change_pct) && stock.last_price > 0);
  const liquid = priced.filter((stock) => (stock.volume_try ?? 0) >= minVolume);
  const pool = liquid.length >= limit * 2 ? liquid : priced;
  const byChange = pool.slice().sort((a, b) => b.change_pct - a.change_pct || a.ticker.localeCompare(b.ticker, "tr-TR"));
  const gainers = byChange.filter((stock) => stock.change_pct > 0).slice(0, limit);
  const losers = byChange.filter((stock) => stock.change_pct < 0).reverse().slice(0, limit);
  return { gainers, losers };
}

export type SignalDistribution = { positive: number; neutral: number; negative: number; total: number };

export function signalDistribution(byLabel: Record<string, number> | null | undefined): SignalDistribution | null {
  if (!byLabel) return null;
  const count = (key: string) => (Number.isFinite(byLabel[key]) ? byLabel[key] : 0);
  const positive = count("VERY_POSITIVE") + count("POSITIVE");
  const negative = count("VERY_NEGATIVE") + count("NEGATIVE");
  const neutral = count("NEUTRAL");
  const total = positive + negative + neutral;
  return total > 0 ? { positive, neutral, negative, total } : null;
}

/** Backend `/api/ai/focus` ve bülten katalizörlerinin ortak alanları. */
export type FocusItem = {
  title: string;
  category: "KAP" | "HABER";
  event_type: string | null;
  event_label: string;
  impact: "POSITIVE" | "NEGATIVE" | "NEUTRAL";
  impact_score: number;
  tickers: string[];
  description: string;
  href: string;
  evaluation_id: number;
  published_at: string | null;
};
export type FocusResponse = { item: FocusItem | null; threshold: number; window_hours: number };

/** Bülten başlık etiketi: güvenilir skor yoksa "Nötr" yerine "Yetersiz veri" denir. */
export function moodLabel(mood: "BULLISH" | "NEUTRAL" | "BEARISH", sampleSize: number | null | undefined): string {
  if (mood === "BULLISH") return "Pozitif skor görünümü";
  if (mood === "BEARISH") return "Negatif skor görünümü";
  return sampleSize ? "Nötr skor görünümü" : "Yetersiz veri";
}
