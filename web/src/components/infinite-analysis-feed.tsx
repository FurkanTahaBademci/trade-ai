"use client";

import Link from "next/link";
import { useMemo } from "react";
import { eventName, formatDate, formatPercent, sourceName } from "@/lib/format";
import type { Evaluation } from "@/lib/types";
import { useInfiniteFeed } from "@/lib/use-infinite-feed";
import { Icon } from "./icon";
import { InfiniteFeedStatus } from "./infinite-feed-status";
import { tierLabel } from "./source-analysis";
import { EmptyState, ScoreMeter, TickerPills } from "./ui";

const PAGE_SIZE = 12;
const analysisCursor = (item: Evaluation) => ({ before: item.created_at, before_id: item.id });
const analysisKey = (item: Evaluation) => item.id;

export function InfiniteAnalysisFeed({
  initialItems,
  source,
  ticker,
  minImpact,
}: {
  initialItems: Evaluation[];
  source?: "news" | "kap";
  ticker?: string;
  minImpact?: number;
}) {
  const filters = useMemo(() => ({ source_type: source, ticker, min_impact: minImpact == null ? undefined : String(minImpact) }), [minImpact, source, ticker]);
  const { items, hasMore, loading, error, loadMore, sentinelRef } = useInfiniteFeed({
    initialItems,
    pageSize: PAGE_SIZE,
    endpoint: "/api/list-feed/analyses",
    filters,
    cursorFor: analysisCursor,
    keyFor: analysisKey,
  });
  const failed = items.filter((item) => item.status === "failed").length;

  return <section aria-busy={loading} aria-live="polite">
    <div className="feed-summary" style={{ borderColor: "var(--border)", background: "var(--surface)" }}><Icon name="spark" size={15} className="text-[var(--primary)]"/><strong className="text-[var(--text)]">{items.length}</strong> değerlendirme gösteriliyor{minImpact != null ? ` (etki ≥ ${minImpact})` : ""}{failed ? <> <span className="text-[var(--border-strong)]">•</span> {failed} başarısız</> : null} <span className="text-[var(--border-strong)]">•</span> Skorlar yatırım tavsiyesi değildir.</div>
    {items.length ? <>
      <div className="panel-flat overflow-hidden">{items.map((item) => <article key={item.id} className="feed-row sm:grid-cols-[72px_minmax(0,1fr)_132px] sm:items-start"><ScoreMeter score={item.impact_score} label="Etki" size={68}/><div className="min-w-0"><div className="mb-1.5 flex flex-wrap gap-1.5"><span className="pill">{sourceName(item.source_type)}</span><span className="pill pill-primary">{eventName(item.event_type)}</span>{item.status === "failed" ? <span className="pill pill-negative">Başarısız</span> : item.status !== "succeeded" ? <span className="pill">İşleniyor</span> : null}</div><Link prefetch={false} href={`/analizler/${item.id}`} className="hover:text-[var(--primary)]"><h2 className="line-clamp-2 text-sm font-medium leading-5">{item.summary || item.error_text || "Değerlendirme işleniyor"}</h2></Link><div className="mt-2"><TickerPills tickers={item.ticker_codes}/></div></div><div className="terminal-mono text-[10px] leading-5 text-[var(--text-muted)]"><p>{formatDate(item.created_at, true)}</p><p>Güven {item.confidence == null ? "—" : formatPercent(item.confidence * 100)}</p><p>{tierLabel(item.tier)}</p></div></article>)}{loading && <AnalysisSkeleton/>}</div>
      <InfiniteFeedStatus sentinelRef={sentinelRef} loading={loading} error={error} hasMore={hasMore} onRetry={() => void loadMore()} endLabel="Tüm değerlendirmeleri gördünüz."/>
    </> : <div className="panel-flat"><EmptyState title={minImpact != null ? `Etkisi ${minImpact} ve üzeri değerlendirme yok` : "AI değerlendirmesi yok"} description={minImpact != null ? "Eşiği düşürmek için \"Tümünü göster\" seçeneğini kullanın." : "LLM özelliği etkinleştirildiğinde haber ve KAP analizleri burada görünür."}/></div>}
  </section>;
}

function AnalysisSkeleton() {
  return <div className="panel-flat min-h-32 animate-pulse p-5" aria-hidden="true"><div className="h-4 w-1/2 rounded bg-[var(--surface-raised)]"/><div className="mt-4 h-3 w-full rounded bg-[var(--surface-raised)]"/><div className="mt-2 h-3 w-2/3 rounded bg-[var(--surface-raised)]"/></div>;
}
