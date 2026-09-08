"use client";

import Link from "next/link";
import type { BacktestRun } from "@/lib/types";
import { formatPercent } from "@/lib/format";
import { useInfiniteFeed } from "@/lib/use-infinite-feed";
import { InfiniteFeedStatus } from "./infinite-feed-status";
import { EmptyState } from "./ui";

const filters = {};
const cursorFor = (run: BacktestRun) => ({ before_id: run.id });
const keyFor = (run: BacktestRun) => run.id;

export function BacktestHistory({ initialItems, selectedId }: { initialItems: BacktestRun[]; selectedId?: number }) {
  const feed = useInfiniteFeed({ initialItems, pageSize: 20, endpoint: "/api/list-feed/backtests", filters, cursorFor, keyFor });
  return <div aria-busy={feed.loading}><div className="panel-flat overflow-hidden">
    {feed.items.length ? feed.items.map((run) => <Link key={run.id} href={`/backtest?run=${run.id}`} aria-current={run.id === selectedId ? "page" : undefined}
      className={`block border-t border-[var(--border)] p-4 first:border-t-0 hover:bg-[var(--surface-hover)] ${run.id === selectedId ? "bg-[var(--primary-soft)]" : ""}`}>
      <div className="flex items-center justify-between gap-3"><span className="text-sm font-semibold">#{run.id} · {run.status === "COMPLETED" ? formatPercent(run.total_return_pct, true) : "—"}</span>
        <span className={`pill ${run.status === "COMPLETED" ? "pill-positive" : ""}`}>{run.status === "COMPLETED" ? "Tamamlandı" : "Yetersiz veri"}</span></div>
      <p className="mt-2 text-[11px] text-[var(--text-muted)]">{run.start_date} → {run.end_date}</p>
    </Link>) : <EmptyState compact title="Henüz koşu yok" description="İlk değerlendirmeyi başlatmak için tarih aralığını seçin."/>}
  </div>{feed.items.length > 0 && <InfiniteFeedStatus {...feed} onRetry={() => void feed.loadMore()} endLabel="Tüm koşuları gördünüz."/>}</div>;
}
