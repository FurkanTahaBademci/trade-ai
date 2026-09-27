"use client";

import Link from "next/link";
import { useCallback, useMemo } from "react";
import { formatDate, relativeTime, sourceName } from "@/lib/format";
import type { NewsArticle } from "@/lib/types";
import { useInfiniteFeed } from "@/lib/use-infinite-feed";
import { InfiniteFeedStatus } from "./infinite-feed-status";
import { EmptyState, TickerPills } from "./ui";

const PAGE_SIZE = 12;
const newsKey = (item: NewsArticle) => item.id;

export function InfiniteNewsFeed({
  initialItems,
  source,
  mode = "smart",
}: {
  initialItems: NewsArticle[];
  source?: string;
  mode?: "smart" | "chronological";
}) {
  const filters = useMemo(() => ({ source, mode }), [source, mode]);

  // Handle pagination strategy based on mode
  // Chronological mode uses timestamp/ID cursor; smart mode uses offset
  const cursorFor = useCallback(
    (item: NewsArticle): Record<string, string | number> => {
      if (mode === "chronological") {
        return { before: item.published_at, before_id: item.id };
      }
      return { offset: initialItems.length };
    },
    [mode, initialItems.length]
  );

  const { items, hasMore, loading, error, loadMore, sentinelRef } = useInfiniteFeed({
    initialItems,
    pageSize: PAGE_SIZE,
    endpoint: "/api/news-feed",
    filters,
    cursorFor,
    keyFor: newsKey,
  });

  if (!items.length) {
    return (
      <div className="panel-flat">
        <EmptyState
          title={mode === "smart" ? "Öne çıkan önemli haber bulunamadı" : "Haber bulunamadı"}
          description={
            mode === "smart"
              ? "Önem puanı pozitif olan yeni haberler değerlendirildiğinde burada görünecek. 'Tüm Haber Akışı' sekmesinden kronolojik akışı inceleyebilirsiniz."
              : "Bu kaynak veya filtreye ait henüz haber girişi yok."
          }
        />
      </div>
    );
  }

  return (
    <section aria-busy={loading} aria-live="polite">
      <div className="mb-3 flex items-center justify-between text-xs text-[var(--text-muted)]">
        <span>
          {items.length} haber listeleniyor
          {mode === "smart" && " · Önem ve güncellik kombinasyonuyla sıralandı"}
        </span>
        <span>Kaydırdıkça yüklenir</span>
      </div>
      <div className="panel-flat overflow-hidden">
        {items.map((item) => (
          <NewsCard key={item.id} item={item} />
        ))}
        {loading && Array.from({ length: 4 }, (_, index) => <NewsSkeleton key={index} />)}
      </div>
      <InfiniteFeedStatus
        sentinelRef={sentinelRef}
        loading={loading}
        error={error}
        hasMore={hasMore}
        onRetry={() => void loadMore()}
        endLabel="Tüm haberleri gördünüz."
      />
    </section>
  );
}

function NewsCard({ item }: { item: NewsArticle }) {
  const sentiment = item.sentiment_score;
  return <article className="feed-row group sm:grid-cols-[110px_minmax(0,1fr)] xl:grid-cols-[110px_minmax(0,1fr)_170px]">
    <div className="flex items-center justify-between gap-2 sm:block"><p className="eyebrow tracking-wider">{sourceName(item.source)}</p><time dateTime={item.published_at} title={formatDate(item.published_at, true)} className="terminal-mono mt-1 text-[10px] text-[var(--text-muted)]">{relativeTime(item.published_at)}</time></div>
    <div className="min-w-0"><Link href={`/haberler/${item.id}`} className="hover:text-[var(--primary)]"><h2 className="text-sm font-medium leading-5">{item.title}</h2></Link>{item.summary && <p className="mt-1 line-clamp-2 text-xs leading-5 text-[var(--text-secondary)]">{item.summary}</p>}<div className="mt-2"><TickerPills tickers={item.ticker_codes}/></div></div>
    <div className="flex flex-wrap items-start gap-2 sm:col-start-2 xl:col-start-auto xl:justify-end"><span className="pill terminal-mono">Etki {item.impact_score ?? "—"}</span>{sentiment != null && <span className={`pill ${sentiment > .15 ? "pill-positive" : sentiment < -.15 ? "pill-negative" : ""}`}>{sentiment > .15 ? "Olumlu" : sentiment < -.15 ? "Olumsuz" : "Nötr"}</span>}</div>
  </article>;
}

function NewsSkeleton() {
  return (
    <div className="min-h-24 animate-pulse p-5" aria-hidden="true">
      <div className="mb-5 flex justify-between">
        <span className="h-3 w-20 rounded bg-[var(--surface-raised)]" />
        <span className="h-3 w-24 rounded bg-[var(--surface-raised)]" />
      </div>
      <div className="h-4 w-11/12 rounded bg-[var(--surface-raised)]" />
      <div className="mt-2 h-4 w-8/12 rounded bg-[var(--surface-raised)]" />
      <div className="mt-5 h-3 w-full rounded bg-[var(--surface-raised)]" />
      <div className="mt-2 h-3 w-9/12 rounded bg-[var(--surface-raised)]" />
    </div>
  );
}
