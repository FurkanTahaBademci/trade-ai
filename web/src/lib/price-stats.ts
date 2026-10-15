import type { Price } from "./types";

export type PriceStats = { dayChange: number | null; low52: number | null; high52: number | null; position52: number | null };

const YEAR_MS = 365 * 86_400_000;

/** Günlük değişim ve son 52 haftanın en düşük/en yüksek kapanışa göre aralığı. */
export function priceStats(prices: Price[]): PriceStats {
  const latest = prices.at(-1);
  if (!latest) return { dayChange: null, low52: null, high52: null, position52: null };
  const previous = prices.at(-2);
  const dayChange = previous && previous.close > 0 ? (latest.close / previous.close - 1) * 100 : null;
  const since = new Date(`${latest.date}T00:00:00`).getTime() - YEAR_MS;
  const window = prices.filter((row) => new Date(`${row.date}T00:00:00`).getTime() >= since);
  const lows = window.map((row) => row.low ?? row.close).filter((value) => value > 0);
  const highs = window.map((row) => row.high ?? row.close).filter((value) => value > 0);
  if (!lows.length || !highs.length) return { dayChange, low52: null, high52: null, position52: null };
  const low52 = Math.min(...lows);
  const high52 = Math.max(...highs);
  const position52 = high52 > low52 ? Math.min(100, Math.max(0, ((latest.close - low52) / (high52 - low52)) * 100)) : null;
  return { dayChange, low52, high52, position52 };
}
