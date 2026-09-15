"use client";

import Link from "next/link";
import { useCallback, useMemo } from "react";
import { formatDate, relativeTime, sourceName } from "@/lib/format";
import type { NewsArticle } from "@/lib/types";
import { useInfiniteFeed } from "@/lib/use-infinite-feed";
import { Icon } from "./icon";
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
      <div className="grid gap-3 lg:grid-cols-2">
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
  const impact = item.impact_score;
  const sentiment = item.sentiment_score;

  return (
    <article className="panel-flat group flex flex-col p-5 transition hover:-translate-y-0.5 hover:border-[var(--border-strong)]">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="eyebrow">{sourceName(item.source)}</span>
          {impact != null && impact > 0 && (
            <span
              className={`pill text-[11px] font-semibold ${
                impact >= 60
                  ? "pill-positive border-[var(--positive)]"
                  : impact >= 40
                  ? "pill-primary"
                  : "bg-[var(--surface-raised)] text-[var(--text-secondary)]"
              }`}
            >
              {impact >= 60 ? "🔥 " : "⚡ "}Etki: {impact}
            </span>
          )}
          {sentiment != null && (
            <span
              className={`pill text-[10px] ${
                sentiment > 0.15
                  ? "text-[var(--positive)]"
                  : sentiment < -0.15
                  ? "text-[var(--negative)]"
                  : "text-[var(--text-muted)]"
              }`}
            >
              {sentiment > 0.15 ? "● Olumlu" : sentiment < -0.15 ? "● Olumsuz" : "● Nötr"}
            </span>
          )}
        </div>

        <span className="flex shrink-0 items-center gap-1 text-[11px] text-[var(--text-muted)]">
          <Icon name="clock" size={12} />
          {relativeTime(item.published_at)}
        </span>
      </div>

      <Link href={`/haberler/${item.id}`}>
        <h2 className="text-base font-semibold leading-6 tracking-[-0.018em] group-hover:text-[var(--primary)]">
          {item.title}
        </h2>
      </Link>

      {item.summary && (
        <p className="mt-2 line-clamp-3 text-sm leading-6 text-[var(--text-secondary)]">
          {item.summary}
        </p>
      )}

      <div className="mt-auto flex items-end justify-between gap-4 pt-5">
        <TickerPills tickers={item.ticker_codes} />
        <Link
          href={`/haberler/${item.id}`}
          className="flex shrink-0 items-center gap-1 text-xs font-medium text-[var(--primary)]"
        >
          Detay <Icon name="arrow" size={13} />
        </Link>
      </div>
    </article>
  );
}

function NewsSkeleton() {
  return (
    <div className="panel-flat min-h-48 animate-pulse p-5" aria-hidden="true">
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
