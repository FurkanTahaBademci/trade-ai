import type { NewsArticle } from "./types";

export type NewsFeedMode = "smart" | "chronological";

export function newsFeedCursor(
  mode: NewsFeedMode,
  lastItem: NewsArticle,
  loadedItemCount: number,
): Record<string, string | number> {
  if (mode === "chronological") {
    return { before: lastItem.published_at, before_id: lastItem.id };
  }
  return { offset: Math.max(0, Math.trunc(loadedItemCount)) };
}
