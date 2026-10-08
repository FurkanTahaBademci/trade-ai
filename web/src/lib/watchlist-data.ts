import { normalizeTicker } from "./turkish";

export const WATCHLIST_STORAGE_KEY = "trade-ai:watchlist";

export function normalizeWatchlist(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const normalized = value
    .filter((item): item is string => typeof item === "string")
    .map((item) => normalizeTicker(item))
    .filter((item) => /^[A-Z0-9]{1,16}$/.test(item));
  return [...new Set(normalized)];
}

