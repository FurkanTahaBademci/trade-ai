"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { formatDate, sourceName } from "@/lib/format";
import type { NewsArticle } from "@/lib/types";
import { Icon } from "./icon";
import { EmptyState, TickerPills } from "./ui";

const PAGE_SIZE = 12;

export function InfiniteNewsFeed({
  initialItems,
  source,
}: {
  initialItems: NewsArticle[];
  source?: string;
}) {
  const [items, setItems] = useState(initialItems);
  const [hasMore, setHasMore] = useState(initialItems.length === PAGE_SIZE);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadingRef = useRef(false);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const loadMore = useCallback(async () => {
    const lastItem = items.at(-1);
    if (!lastItem || !hasMore || loadingRef.current) return;

    loadingRef.current = true;
    setLoading(true);
    setError(null);

    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      before: lastItem.published_at,
      before_id: String(lastItem.id),
    });
    if (source) params.set("source", source);

    try {
      const response = await fetch(`/api/news-feed?${params}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const nextItems = (await response.json()) as NewsArticle[];
      setItems((current) => {
        const knownIds = new Set(current.map((item) => item.id));
        return [...current, ...nextItems.filter((item) => !knownIds.has(item.id))];
      });
      setHasMore(nextItems.length === PAGE_SIZE);
    } catch {
      setError("Yeni haberler yüklenemedi. Bağlantıyı kontrol edip tekrar deneyin.");
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, [hasMore, items, source]);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) void loadMore();
      },
      { rootMargin: "500px 0px" },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loadMore]);

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
    <div ref={sentinelRef} className="flex min-h-24 items-center justify-center py-6">
      {error ? <div className="text-center"><p className="text-xs text-[var(--negative)]">{error}</p><button type="button" onClick={() => void loadMore()} className="mt-3 rounded-[10px] border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs font-medium transition hover:bg-[var(--surface-hover)]">Tekrar dene</button></div>
        : loading ? <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]"><span className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--primary)]"/>Haberler yükleniyor</div>
        : !hasMore ? <p className="text-xs text-[var(--text-muted)]">Tüm haberleri gördünüz.</p>
        : <span className="sr-only">Daha fazla haber için aşağı kaydırın</span>}
    </div>
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
