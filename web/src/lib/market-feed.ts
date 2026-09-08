import type { MarketFeedItem } from "./types";

function finiteScore(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function normalizeMarketFeed(value: unknown): MarketFeedItem[] {
  if (!Array.isArray(value)) return [];
  const items = new Map<string, MarketFeedItem>();
  for (const row of value) {
    if (!row || typeof row !== "object") continue;
    const candidate = row as Record<string, unknown>;
    const ticker = typeof candidate.ticker === "string" ? candidate.ticker.trim().toUpperCase() : "";
    const name = typeof candidate.name === "string" ? candidate.name.trim() : "";
    if (!/^[A-Z0-9]{1,16}$/.test(ticker) || !name) continue;
    items.set(ticker, {
      ticker,
      name,
      composite_score: finiteScore(candidate.composite_score),
      signal_label: typeof candidate.signal_label === "string" ? candidate.signal_label : null,
    });
  }
  return [...items.values()];
}

export function searchMarketFeed(
  items: MarketFeedItem[],
  query: string,
  limit = 8,
): MarketFeedItem[] {
  const value = query.trim().toLocaleUpperCase("tr-TR");
  if (limit <= 0) return [];
  return items
    .filter((item) => (
      !value
      || item.ticker.includes(value)
      || item.name.toLocaleUpperCase("tr-TR").includes(value)
    ))
    .sort((a, b) => {
      const rank = (item: MarketFeedItem) => (
        item.ticker === value ? 0 : item.ticker.startsWith(value) ? 1 : 2
      );
      return rank(a) - rank(b) || a.ticker.localeCompare(b.ticker, "tr-TR");
    })
    .slice(0, limit);
}

export async function fetchMarketFeed(signal?: AbortSignal): Promise<MarketFeedItem[]> {
  const response = await fetch("/api/market-feed", { cache: "no-store", signal });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data: unknown = await response.json();
  if (!Array.isArray(data)) throw new Error("Geçersiz market verisi");
  return normalizeMarketFeed(data);
}
