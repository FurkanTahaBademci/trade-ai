"use client";

import Link from "next/link";
import { useMemo } from "react";
import { formatDate, sourceName } from "@/lib/format";
import type { NewsArticle } from "@/lib/types";
import { useInfiniteFeed } from "@/lib/use-infinite-feed";
import { Icon } from "./icon";
import { InfiniteFeedStatus } from "./infinite-feed-status";
import { EmptyState, TickerPills } from "./ui";

const PAGE_SIZE = 12;
const newsCursor = (item: NewsArticle) => ({ before: item.published_at, before_id: item.id });
const newsKey = (item: NewsArticle) => item.id;

export function InfiniteNewsFeed({
  initialItems,
  source,
}: {
  initialItems: NewsArticle[];
  source?: string;
}) {
  const filters = useMemo(() => ({ source }), [source]);
  const { items, hasMore, loading, error, loadMore, sentinelRef } = useInfiniteFeed({
    initialItems,
    pageSize: PAGE_SIZE,
    endpoint: "/api/news-feed",
    filters,
    cursorFor: newsCursor,
    keyFor: newsKey,
  });

  if (!items.length) {
    return <div className="panel-flat"><EmptyState /></div>;
  }

  return <section aria-busy={loading} aria-live="polite">
    <div className="mb-3 flex items-center justify-between text-xs text-[var(--text-muted)]">
      <span>{items.length} haber gösteriliyor</span>
      <span>Kaydırdıkça yenileri yüklenir</span>
    </div>
    <div className="grid gap-3 lg:grid-cols-2">
      {items.map((item) => <NewsCard key={item.id} item={item}/>) }
      {loading && Array.from({ length: 4 }, (_, index) => <NewsSkeleton key={index}/>) }
    </div>
    <InfiniteFeedStatus sentinelRef={sentinelRef} loading={loading} error={error} hasMore={hasMore} onRetry={() => void loadMore()} endLabel="Tüm haberleri gördünüz."/>
  </section>;
}

function NewsCard({ item }: { item: NewsArticle }) {
  return <article className="panel-flat group flex flex-col p-5 transition hover:-translate-y-0.5 hover:border-[var(--border-strong)]">
    <div className="mb-4 flex items-center justify-between gap-3"><span className="eyebrow">{sourceName(item.source)}</span><span className="flex shrink-0 items-center gap-1 text-[11px] text-[var(--text-muted)]"><Icon name="clock" size={12}/>{formatDate(item.published_at, true)}</span></div>
    <Link href={`/haberler/${item.id}`}><h2 className="text-base font-semibold leading-6 tracking-[-0.018em] group-hover:text-[var(--primary)]">{item.title}</h2></Link>
    {item.summary && <p className="mt-2 line-clamp-3 text-sm leading-6 text-[var(--text-secondary)]">{item.summary}</p>}
    <div className="mt-auto flex items-end justify-between gap-4 pt-5"><TickerPills tickers={item.ticker_codes}/><Link href={`/haberler/${item.id}`} className="flex shrink-0 items-center gap-1 text-xs font-medium text-[var(--primary)]">Detay <Icon name="arrow" size={13}/></Link></div>
  </article>;
}

function NewsSkeleton() {
  return <div className="panel-flat min-h-48 animate-pulse p-5" aria-hidden="true">
    <div className="mb-5 flex justify-between"><span className="h-3 w-20 rounded bg-[var(--surface-raised)]"/><span className="h-3 w-24 rounded bg-[var(--surface-raised)]"/></div>
    <div className="h-4 w-11/12 rounded bg-[var(--surface-raised)]"/><div className="mt-2 h-4 w-8/12 rounded bg-[var(--surface-raised)]"/>
    <div className="mt-5 h-3 w-full rounded bg-[var(--surface-raised)]"/><div className="mt-2 h-3 w-9/12 rounded bg-[var(--surface-raised)]"/>
  </div>;
}
