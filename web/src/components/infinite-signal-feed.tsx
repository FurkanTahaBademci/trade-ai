"use client";

import Link from "next/link";
import { useMemo } from "react";
import { componentName, formatDate, formatPercent, signalName } from "@/lib/format";
import type { CompositeSignal } from "@/lib/types";
import { useInfiniteFeed } from "@/lib/use-infinite-feed";
import { Icon } from "./icon";
import { InfiniteFeedStatus } from "./infinite-feed-status";
import { EmptyState, ScoreMeter } from "./ui";

const PAGE_SIZE = 15;
const signalCursor = (item: CompositeSignal) => ({
  after_score: item.composite_score,
  after_ticker: item.ticker,
  after_id: item.id,
});
const signalKey = (item: CompositeSignal) => item.id;

export function InfiniteSignalFeed({
  initialItems,
  label,
}: {
  initialItems: CompositeSignal[];
  label?: string;
}) {
  const filters = useMemo(() => ({ label }), [label]);
  const { items, hasMore, loading, error, loadMore, sentinelRef } = useInfiniteFeed({
    initialItems,
    pageSize: PAGE_SIZE,
    endpoint: "/api/list-feed/signals",
    filters,
    cursorFor: signalCursor,
    keyFor: signalKey,
  });

  return <section aria-busy={loading} aria-live="polite">
    <div className="feed-summary" style={{ borderColor: "var(--border)", background: "var(--surface)" }}><Icon name="activity" size={15} className="text-[var(--primary)]"/><strong className="text-[var(--text)]">{items.length}</strong> hisse gösteriliyor <span className="text-[var(--border-strong)]">•</span> Kaydırdıkça sıralamanın devamı yüklenir.</div>
    {items.length ? <>
      <div className="table-shell overflow-x-auto"><table className="data-table min-w-[720px]"><caption>Bileşik skora göre sıralı hisseler · skor aralığı 0–100</caption><thead><tr><th scope="col">#</th><th scope="col">Hisse / tarih</th><th scope="col">Skor</th><th scope="col">Bileşenler</th><th scope="col">Sinyal</th><th scope="col" className="text-right">Güven</th></tr></thead><tbody>{items.map((item, index) => <tr key={item.id}><td className="terminal-mono text-[var(--text-muted)]">{index + 1}</td><td><Link href={`/piyasalar/${item.ticker}`} className="terminal-mono font-semibold text-[var(--primary)] hover:underline">{item.ticker}</Link><p className="terminal-mono mt-1 text-[10px] text-[var(--text-muted)]">{formatDate(item.as_of_date)}</p></td><td><ScoreMeter score={item.composite_score} label="Skor" size={64}/></td><td><div className="grid min-w-[220px] grid-cols-2 gap-x-4 gap-y-1.5">{Object.entries(item.component_scores).map(([name, score]) => <div key={name}><div className="mb-1 flex justify-between gap-2 text-[10px] text-[var(--text-secondary)]"><span>{componentName(name)}</span><span className="terminal-mono">{Math.round(score)}</span></div><div className="h-0.5 bg-[var(--border)]"><div className="h-full bg-[var(--info)]" style={{ width: `${Math.max(0, Math.min(100, score))}%` }}/></div></div>)}</div></td><td><span className={`pill whitespace-nowrap ${item.signal_label.includes("POSITIVE") ? "pill-positive" : item.signal_label.includes("NEGATIVE") ? "pill-negative" : ""}`}>{signalName(item.signal_label)}</span></td><td className="terminal-mono text-right">{formatPercent(item.confidence * 100)}</td></tr>)}</tbody></table>{loading && <SignalSkeleton/>}</div>
      <InfiniteFeedStatus sentinelRef={sentinelRef} loading={loading} error={error} hasMore={hasMore} onRetry={() => void loadMore()} endLabel="Tüm sinyalleri gördünüz."/>
    </> : <div className="panel-flat"><EmptyState title="Bileşik skor henüz yok" description="Sinyal motoru ilk kez çalıştığında en az iki veri bileşeni bulunan hisseler burada sıralanacak."/></div>}
  </section>;
}

function SignalSkeleton() {
  return <div className="panel-flat min-h-32 animate-pulse p-5" aria-hidden="true"><div className="h-4 w-1/3 rounded bg-[var(--surface-raised)]"/><div className="mt-4 h-3 w-full rounded bg-[var(--surface-raised)]"/><div className="mt-2 h-3 w-3/4 rounded bg-[var(--surface-raised)]"/></div>;
}
