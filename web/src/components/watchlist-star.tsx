"use client";

import { useWatchlist } from "@/lib/watchlist";
import { Icon } from "./icon";

export function WatchlistStar({ ticker, size = 18 }: { ticker: string; size?: number }) {
  const { isWatched, toggle } = useWatchlist();
  const watched = isWatched(ticker);
  return (
    <button
      type="button"
      onClick={(event) => { event.preventDefault(); event.stopPropagation(); toggle(ticker); }}
      aria-pressed={watched}
      aria-label={watched ? `${ticker} izleme listesinden çıkar` : `${ticker} izleme listesine ekle`}
      className={`icon-button ${watched ? "!text-[var(--warning)]" : ""}`}
    >
      <Icon name="star" size={size} fill={watched ? "currentColor" : "none"} />
    </button>
  );
}
