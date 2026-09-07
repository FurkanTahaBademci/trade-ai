"use client";

import Link from "next/link";
import { useMemo } from "react";
import { componentName, formatDate, formatPercent, signalName } from "@/lib/format";
import type { CompositeSignal } from "@/lib/types";
import { useInfiniteFeed } from "@/lib/use-infinite-feed";
import { Icon } from "./icon";
import { InfiniteFeedStatus } from "./infinite-feed-status";
import { EmptyState, ScoreRing } from "./ui";

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
    <div className="mb-5 flex items-center gap-3 rounded-[12px] border px-4 py-3 text-xs text-[var(--text-secondary)]" style={{ borderColor: "var(--border)", background: "var(--surface)" }}><Icon name="activity" size={15} className="text-[var(--primary)]"/><strong className="text-[var(--text)]">{items.length}</strong> hisse gösteriliyor <span className="text-[var(--border-strong)]">•</span> Kaydırdıkça sıralamanın devamı yüklenir.</div>
    {items.length ? <>
      <div className="space-y-3">{items.map((item, index) => <Link href={`/piyasalar/${item.ticker}`} key={item.id} className="panel-flat group grid gap-4 p-4 transition hover:border-[var(--border-strong)] sm:grid-cols-[42px_72px_130px_minmax(240px,1fr)_130px_20px] sm:items-center sm:p-5"><span className="text-center text-xs font-semibold text-[var(--text-muted)]">#{index + 1}</span><ScoreRing score={item.composite_score} label="Skor" size={62}/><div><p className="text-base font-semibold text-[var(--primary)]">{item.ticker}</p><p className="mt-1 text-[11px] text-[var(--text-muted)]">{formatDate(item.as_of_date)}</p></div><div className="grid grid-cols-2 gap-x-5 gap-y-2">{Object.entries(item.component_scores).map(([name, score]) => <div key={name}><div className="mb-1 flex justify-between text-[10px] text-[var(--text-muted)]"><span>{componentName(name)}</span><span>{Math.round(score)}</span></div><div className="h-1 rounded-full bg-[var(--border)]"><div className="h-1 rounded-full bg-[var(--primary)]" style={{ width: `${score}%` }}/></div></div>)}</div><div><span className={`pill ${item.signal_label.includes("POSITIVE") ? "pill-positive" : item.signal_label.includes("NEGATIVE") ? "pill-negative" : ""}`}>{signalName(item.signal_label)}</span><p className="mt-2 text-[11px] text-[var(--text-muted)]">Güven {formatPercent(item.confidence * 100)}</p></div><Icon name="chevron" size={16} className="hidden text-[var(--text-muted)] sm:block"/></Link>)}{loading && <SignalSkeleton/>}</div>
      <InfiniteFeedStatus sentinelRef={sentinelRef} loading={loading} error={error} hasMore={hasMore} onRetry={() => void loadMore()} endLabel="Tüm sinyalleri gördünüz."/>
    </> : <div className="panel-flat"><EmptyState title="Bileşik skor henüz yok" description="Sinyal motoru ilk kez çalıştığında en az iki veri bileşeni bulunan hisseler burada sıralanacak."/></div>}
  </section>;
}

function SignalSkeleton() {
  return <div className="panel-flat min-h-32 animate-pulse p-5" aria-hidden="true"><div className="h-4 w-1/3 rounded bg-[var(--surface-raised)]"/><div className="mt-4 h-3 w-full rounded bg-[var(--surface-raised)]"/><div className="mt-2 h-3 w-3/4 rounded bg-[var(--surface-raised)]"/></div>;
}
