"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import type { Instrument, MarketHeatmapStock } from "@/lib/types";
import { formatMoney, formatNumber, formatPercent, signalName } from "@/lib/format";
import { Icon } from "./icon";
import { InfiniteFeedStatus } from "./infinite-feed-status";
import { EmptyState } from "./ui";
import { WatchlistStar } from "./watchlist-star";

import { matchesTurkishSearch, rankTurkishSearchMatch } from "@/lib/turkish";

const BATCH_SIZE = 20;
type SortKey = "ticker" | "change" | "volume" | "score";
const SORT_LABELS: Record<SortKey, string> = { ticker: "Koda göre", change: "Günlük değişim", volume: "İşlem hacmi", score: "Bileşik skor" };

export function InstrumentList({ instruments, quotes = {} }: { instruments: Instrument[]; quotes?: Record<string, MarketHeatmapStock> }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("ticker");
  const [visibleCount, setVisibleCount] = useState(BATCH_SIZE);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const filtered = useMemo(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      if (sort === "ticker") return instruments;
      const value = (item: Instrument) => {
        const quote = quotes[item.ticker];
        if (!quote) return Number.NEGATIVE_INFINITY;
        return sort === "change" ? quote.change_pct : sort === "volume" ? quote.volume_try : quote.composite_score ?? Number.NEGATIVE_INFINITY;
      };
      return [...instruments].sort((a, b) => value(b) - value(a) || a.ticker.localeCompare(b.ticker, "tr-TR"));
    }
    return instruments
      .filter((item) => matchesTurkishSearch(trimmed, item.ticker, item.name))
      .sort((a, b) => {
        const rankA = rankTurkishSearchMatch(trimmed, a.ticker, a.name);
        const rankB = rankTurkishSearchMatch(trimmed, b.ticker, b.name);
        return rankA - rankB || a.ticker.localeCompare(b.ticker, "tr-TR");
      });
  }, [instruments, query, quotes, sort]);

  const visible = filtered.slice(0, visibleCount);
  const hasMore = visibleCount < filtered.length;

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisibleCount((current) => Math.min(current + BATCH_SIZE, filtered.length));
        }
      },
      { rootMargin: "300px 0px" },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [filtered.length, hasMore, visibleCount]);

  return <>
    <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><label className="relative block w-full max-w-md"><Icon name="search" size={16} className="absolute left-3 top-3 text-[var(--text-muted)]"/><input className="input pl-9" value={query} onChange={(event) => { setQuery(event.target.value); setVisibleCount(BATCH_SIZE); }} placeholder="Kod veya şirket adıyla ara" aria-label="Hisse ara"/></label><div className="flex items-center gap-3"><select className="input w-auto py-1.5 text-xs" value={sort} onChange={(event) => { setSort(event.target.value as SortKey); setVisibleCount(BATCH_SIZE); }} aria-label="Sıralama">{(Object.keys(SORT_LABELS) as SortKey[]).map((key) => <option key={key} value={key}>{SORT_LABELS[key]}</option>)}</select><p className="text-xs text-[var(--text-muted)]">{visible.length} / {filtered.length} hisse gösteriliyor</p></div></div>
    {filtered.length ? <section aria-live="polite"><div className="table-shell overflow-x-auto"><table className="data-table min-w-[820px]"><thead><tr><th className="w-10"><span className="sr-only">İşlem</span></th><th>Hisse</th><th>Şirket</th><th className="text-right">Son fiyat</th><th className="text-right">Değişim</th><th className="text-right">Hacim</th><th className="text-right">Bileşik skor</th><th className="w-10"><span className="sr-only">İşlem</span></th></tr></thead><tbody>{visible.map((item) => { const quote = quotes[item.ticker]; return <tr key={item.ticker}><td><WatchlistStar ticker={item.ticker} size={16}/></td><td><Link href={`/piyasalar/${item.ticker}`} className="terminal-mono font-semibold text-[var(--primary)]">{item.ticker}</Link></td><td className="font-medium">{item.name}{quote?.sector && <span className="block text-[10px] font-normal text-[var(--text-muted)]">{quote.sector}</span>}</td><td className="terminal-mono text-right">{quote ? formatMoney(quote.last_price) : "—"}</td><td className={`terminal-mono text-right ${!quote ? "text-[var(--text-muted)]" : quote.change_pct >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"}`}>{quote ? formatPercent(quote.change_pct, true) : "—"}</td><td className="terminal-mono text-right text-[var(--text-secondary)]">{quote?.volume_try ? formatMoney(quote.volume_try, true) : "—"}</td><td className="text-right">{quote?.composite_score != null ? <span title={signalName(quote.signal_label ?? "")}>{formatNumber(quote.composite_score, 0)}</span> : <span className="text-[var(--text-muted)]">—</span>}</td><td><Link href={`/piyasalar/${item.ticker}`} aria-label={`${item.ticker} detayını aç`} className="text-[var(--text-muted)]"><Icon name="chevron" size={16}/></Link></td></tr>; })}</tbody></table></div><InfiniteFeedStatus sentinelRef={sentinelRef} loading={false} error={null} hasMore={hasMore} onRetry={() => undefined} endLabel="Tüm hisseleri gördünüz."/></section> : <div className="panel-flat"><EmptyState title="Hisse bulunamadı" description="Arama ifadenizi değiştirerek tekrar deneyin."/></div>}
  </>;
}
