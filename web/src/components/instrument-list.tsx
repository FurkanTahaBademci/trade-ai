"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import type { InstrumentSummary, MarketHeatmapStock } from "@/lib/types";
import { formatMoney, formatNumber, formatPercent, signalName } from "@/lib/format";
import { MARKETS_SORT_KEYS, MARKETS_SORT_LABELS, defaultOrder, type MarketsSortKey, type SortOrder } from "@/lib/markets-view";
import { Icon } from "./icon";
import { InfiniteFeedStatus } from "./infinite-feed-status";
import { EmptyState } from "./ui";
import { WatchlistStar } from "./watchlist-star";

import { matchesTurkishSearch, rankTurkishSearchMatch } from "@/lib/turkish";

const BATCH_SIZE = 20;

type Props = {
  instruments: InstrumentSummary[];
  quotes?: Record<string, MarketHeatmapStock>;
  sort?: MarketsSortKey;
  order?: SortOrder;
  /** Sütun başlığına tıklama (yön değiştirme ebeveynde). */
  onSort?: (column: MarketsSortKey) => void;
  onSortChange?: (sort: MarketsSortKey, order: SortOrder) => void;
};

function quoteValue(sort: Exclude<MarketsSortKey, "ticker">, quote: MarketHeatmapStock | undefined) {
  if (!quote) return null;
  const value = sort === "price" ? quote.last_price : sort === "change" ? quote.change_pct : sort === "volume" ? quote.volume_try : quote.composite_score;
  return value == null || !Number.isFinite(value) ? null : value;
}

export function InstrumentList({ instruments, quotes = {}, sort = "ticker", order = "asc", onSort, onSortChange }: Props) {
  const [query, setQuery] = useState("");
  const [visibleCount, setVisibleCount] = useState(BATCH_SIZE);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const filtered = useMemo(() => {
    const trimmed = query.trim();
    const direction = order === "asc" ? 1 : -1;
    const byTicker = (a: InstrumentSummary, b: InstrumentSummary) => a.ticker.localeCompare(b.ticker, "tr-TR");
    if (trimmed && sort === "ticker" && order === "asc") {
      // Varsayılan sıralamada arama sonucu alaka sırasıyla gelir.
      return instruments
        .filter((item) => matchesTurkishSearch(trimmed, item.ticker, item.name))
        .sort((a, b) => rankTurkishSearchMatch(trimmed, a.ticker, a.name) - rankTurkishSearchMatch(trimmed, b.ticker, b.name) || byTicker(a, b));
    }
    const base = trimmed ? instruments.filter((item) => matchesTurkishSearch(trimmed, item.ticker, item.name)) : [...instruments];
    if (sort === "ticker") return base.sort((a, b) => direction * byTicker(a, b));
    return base.sort((a, b) => {
      const valueA = quoteValue(sort, quotes[a.ticker]);
      const valueB = quoteValue(sort, quotes[b.ticker]);
      // Verisi olmayan hisseler yönden bağımsız olarak sonda kalır.
      if (valueA == null || valueB == null) return valueA == null ? (valueB == null ? byTicker(a, b) : 1) : -1;
      return direction * (valueA - valueB) || byTicker(a, b);
    });
  }, [instruments, query, quotes, sort, order]);

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

  const resetPaging = () => setVisibleCount(BATCH_SIZE);
  const header = (column: MarketsSortKey, label: string, className = "") => {
    const active = sort === column;
    return <th scope="col" className={className} aria-sort={active ? (order === "asc" ? "ascending" : "descending") : undefined}>
      <button type="button" onClick={() => { onSort?.(column); resetPaging(); }} className={`inline-flex items-center gap-1 uppercase tracking-[inherit] transition hover:text-[var(--text)] ${active ? "text-[var(--text)]" : ""}`} title={`${MARKETS_SORT_LABELS[column]} sütununa göre sırala`}>
        {label}{active && <span aria-hidden="true">{order === "asc" ? "↑" : "↓"}</span>}
      </button>
    </th>;
  };

  return <>
    <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
      <label className="relative block w-full max-w-md"><Icon name="search" size={16} className="absolute left-3 top-3 text-[var(--text-muted)]"/><input className="input pl-9" value={query} onChange={(event) => { setQuery(event.target.value); resetPaging(); }} placeholder="Kod veya şirket adıyla ara" aria-label="Hisse ara"/></label>
      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        <select className="input w-auto py-1.5 text-xs" value={sort} onChange={(event) => { const next = event.target.value as MarketsSortKey; onSortChange?.(next, defaultOrder(next)); resetPaging(); }} aria-label="Sıralama ölçütü">{MARKETS_SORT_KEYS.map((key) => <option key={key} value={key}>{MARKETS_SORT_LABELS[key]}</option>)}</select>
        <button type="button" className="icon-button h-10 w-auto px-3 text-xs" onClick={() => { onSortChange?.(sort, order === "asc" ? "desc" : "asc"); resetPaging(); }} aria-label={`Sıralama yönü: ${order === "asc" ? "artan" : "azalan"}. Değiştir`}>{order === "asc" ? "↑ Artan" : "↓ Azalan"}</button>
        <p className="text-xs text-[var(--text-muted)]">{visible.length} / {filtered.length} hisse</p>
      </div>
    </div>
    {filtered.length ? <section aria-live="polite"><div className="table-shell overflow-x-auto"><table className="data-table data-table-compact sm:min-w-[720px]"><caption className="sr-only">Hisse listesi · {MARKETS_SORT_LABELS[sort]} ({order === "asc" ? "artan" : "azalan"})</caption><thead><tr>{header("ticker", "Hisse", "sticky-col")}<th scope="col" className="hidden sm:table-cell">Şirket</th>{header("price", "Fiyat", "text-right")}{header("change", "Değişim", "text-right")}{header("volume", "Hacim", "hidden text-right md:table-cell")}{header("score", "Skor", "text-right")}<th className="hidden w-10 sm:table-cell"><span className="sr-only">Detay</span></th></tr></thead><tbody>{visible.map((item) => { const quote = quotes[item.ticker]; return <tr key={item.ticker}><td className="sticky-col"><div className="flex items-center gap-1.5"><span className="hidden sm:block"><WatchlistStar ticker={item.ticker} size={16}/></span><div className="min-w-0"><Link href={`/piyasalar/${item.ticker}`} className="terminal-mono font-semibold text-[var(--primary)]">{item.ticker}</Link><span className="block max-w-[30vw] truncate text-xs text-[var(--text-muted)] sm:hidden" title={item.name}>{item.name}</span></div></div></td><td className="hidden font-medium sm:table-cell">{item.name}{quote?.sector && <span className="block text-xs font-normal text-[var(--text-muted)]">{quote.sector}</span>}</td><td className="terminal-mono whitespace-nowrap text-right">{quote ? formatMoney(quote.last_price) : "—"}</td><td className={`terminal-mono whitespace-nowrap text-right ${!quote ? "text-[var(--text-muted)]" : quote.change_pct >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"}`}>{quote ? formatPercent(quote.change_pct, true) : "—"}</td><td className="terminal-mono hidden whitespace-nowrap text-right text-[var(--text-secondary)] md:table-cell">{quote?.volume_try ? formatMoney(quote.volume_try, true) : "—"}</td><td className="text-right">{quote?.composite_score != null ? <span title={signalName(quote.signal_label ?? "")}>{formatNumber(quote.composite_score, 0)}</span> : <span className="text-[var(--text-muted)]" title="Bileşik skor henüz hesaplanmadı">—</span>}</td><td className="hidden sm:table-cell"><Link href={`/piyasalar/${item.ticker}`} aria-label={`${item.ticker} detayını aç`} className="text-[var(--text-muted)]"><Icon name="chevron" size={16}/></Link></td></tr>; })}</tbody></table></div><InfiniteFeedStatus sentinelRef={sentinelRef} loading={false} error={null} hasMore={hasMore} onRetry={() => undefined} endLabel="Tüm hisseleri gördünüz."/></section> : <div className="panel-flat"><EmptyState title="Hisse bulunamadı" description="Arama ifadenizi değiştirerek tekrar deneyin."/></div>}
  </>;
}
