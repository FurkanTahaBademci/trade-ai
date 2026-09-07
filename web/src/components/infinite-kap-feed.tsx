"use client";

import Link from "next/link";
import { formatDate } from "@/lib/format";
import type { Disclosure } from "@/lib/types";
import { useInfiniteFeed } from "@/lib/use-infinite-feed";
import { Icon } from "./icon";
import { InfiniteFeedStatus } from "./infinite-feed-status";
import { EmptyState, TickerPills } from "./ui";

const PAGE_SIZE = 15;
const noFilters = {};
const kapCursor = (item: Disclosure) => ({
  before: item.published_at,
  before_index: item.disclosure_index,
});
const kapKey = (item: Disclosure) => item.disclosure_index;

export function InfiniteKapFeed({ initialItems }: { initialItems: Disclosure[] }) {
  const { items, hasMore, loading, error, loadMore, sentinelRef } = useInfiniteFeed({
    initialItems,
    pageSize: PAGE_SIZE,
    endpoint: "/api/list-feed/kap",
    filters: noFilters,
    cursorFor: kapCursor,
    keyFor: kapKey,
  });

  if (!items.length) return <div className="panel-flat"><EmptyState /></div>;

  return <section aria-busy={loading} aria-live="polite">
    <div className="mb-3 flex items-center justify-between text-xs text-[var(--text-muted)]"><span>{items.length} bildirim gösteriliyor</span><span>Kaydırdıkça yenileri yüklenir</span></div>
    <div className="panel-flat overflow-hidden">
      {items.map((item, index) => <Link href={`/kap/${item.disclosure_index}`} key={item.disclosure_index} className={`group grid gap-4 p-4 transition hover:bg-[var(--surface-hover)] sm:grid-cols-[150px_minmax(0,1fr)_110px_20px] sm:items-center sm:p-5 ${index ? "border-t" : ""}`} style={{ borderColor: "var(--border)" }}><div><p className="text-xs font-medium">{formatDate(item.published_at, true)}</p><p className="mt-1 text-[10px] uppercase tracking-wider text-[var(--text-muted)]">#{item.disclosure_index}</p></div><div className="min-w-0"><div className="mb-2"><TickerPills tickers={item.ticker_codes}/></div><h2 className="line-clamp-2 text-sm font-medium leading-5 group-hover:text-[var(--primary)]">{item.subject || item.summary || item.kap_title}</h2><p className="mt-1 text-[11px] text-[var(--text-muted)]">{item.disclosure_class || item.disclosure_category || "Şirket bildirimi"}</p></div><div className="text-xs text-[var(--text-secondary)]">{item.attachment_count ? <span className="flex items-center gap-1.5"><Icon name="file" size={14}/>{item.attachment_count} ek</span> : "Ek yok"}</div><Icon name="chevron" size={16} className="hidden text-[var(--text-muted)] sm:block"/></Link>)}
      {loading && <div className="animate-pulse border-t p-5" style={{ borderColor: "var(--border)" }}><div className="h-4 w-2/3 rounded bg-[var(--surface-raised)]"/><div className="mt-3 h-3 w-1/3 rounded bg-[var(--surface-raised)]"/></div>}
    </div>
    <InfiniteFeedStatus sentinelRef={sentinelRef} loading={loading} error={error} hasMore={hasMore} onRetry={() => void loadMore()} endLabel="Tüm KAP bildirimlerini gördünüz."/>
  </section>;
}
