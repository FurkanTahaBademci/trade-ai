"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import type { Instrument } from "@/lib/types";
import { Icon } from "./icon";
import { InfiniteFeedStatus } from "./infinite-feed-status";
import { EmptyState } from "./ui";
import { WatchlistStar } from "./watchlist-star";

const BATCH_SIZE = 20;

export function InstrumentList({ instruments }: { instruments: Instrument[] }) {
  const [query, setQuery] = useState("");
  const [visibleCount, setVisibleCount] = useState(BATCH_SIZE);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const filtered = useMemo(() => { const value = query.trim().toLocaleUpperCase("tr-TR"); return instruments.filter((item) => !value || item.ticker.includes(value) || item.name.toLocaleUpperCase("tr-TR").includes(value)); }, [instruments, query]);
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
    <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><label className="relative block w-full max-w-md"><Icon name="search" size={16} className="absolute left-3 top-3 text-[var(--text-muted)]"/><input className="input pl-9" value={query} onChange={(event) => { setQuery(event.target.value); setVisibleCount(BATCH_SIZE); }} placeholder="Kod veya şirket adıyla ara" aria-label="Hisse ara"/></label><p className="text-xs text-[var(--text-muted)]">{visible.length} / {filtered.length} hisse gösteriliyor</p></div>
    {filtered.length ? <section aria-live="polite"><div className="table-shell overflow-x-auto"><table className="data-table min-w-[680px]"><thead><tr><th className="w-10"></th><th>Hisse</th><th>Şirket</th><th>Merkez</th><th>Durum</th><th className="w-10"></th></tr></thead><tbody>{visible.map((item) => <tr key={item.ticker}><td><WatchlistStar ticker={item.ticker} size={16}/></td><td><Link href={`/piyasalar/${item.ticker}`} className="font-semibold text-[var(--primary)]">{item.ticker}</Link></td><td className="font-medium">{item.name}</td><td className="text-[var(--text-secondary)]">{item.city || "—"}</td><td><span className="pill pill-positive"><span className="h-1.5 w-1.5 rounded-full bg-[var(--positive)]"/>Aktif</span></td><td><Link href={`/piyasalar/${item.ticker}`} className="text-[var(--text-muted)]"><Icon name="chevron" size={16}/></Link></td></tr>)}</tbody></table></div><InfiniteFeedStatus sentinelRef={sentinelRef} loading={false} error={null} hasMore={hasMore} onRetry={() => undefined} endLabel="Tüm hisseleri gördünüz."/></section> : <div className="panel-flat"><EmptyState title="Hisse bulunamadı" description="Arama ifadenizi değiştirerek tekrar deneyin."/></div>}
  </>;
}
