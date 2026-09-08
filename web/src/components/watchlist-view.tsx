"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { MarketFeedItem } from "@/lib/types";
import { signalName } from "@/lib/format";
import { EmptyState } from "@/components/ui";
import { Icon } from "@/components/icon";
import { WatchlistStar } from "@/components/watchlist-star";
import { useWatchlist } from "@/lib/watchlist";

export function WatchlistView() {
  const { tickers } = useWatchlist();
  const [items, setItems] = useState<MarketFeedItem[] | null>(null);

  useEffect(() => {
    if (!tickers.length) { setItems([]); return; }
    let cancelled = false;
    fetch("/api/market-feed", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : []))
      .then((data: MarketFeedItem[]) => { if (!cancelled) setItems(Array.isArray(data) ? data : []); })
      .catch(() => { if (!cancelled) setItems([]); });
    return () => { cancelled = true; };
  }, [tickers.length]);

  const watched = (items ?? []).filter((item) => tickers.includes(item.ticker));

  if (!tickers.length) return <div className="panel-flat"><EmptyState title="İzleme listeniz boş" description="Piyasalar sayfasında veya bir hisse detayında yıldıza tıklayarak buraya ekleyin."/></div>;
  if (items == null) return <p className="text-sm text-[var(--text-muted)]">Yükleniyor...</p>;

  return <div className="table-shell overflow-x-auto"><table className="data-table min-w-[560px]"><thead><tr><th className="w-10"></th><th>Hisse</th><th>Şirket</th><th>Bileşik skor</th><th className="w-10"></th></tr></thead><tbody>
    {watched.map((item) => <tr key={item.ticker}>
      <td><WatchlistStar ticker={item.ticker} size={16}/></td>
      <td><Link href={`/piyasalar/${item.ticker}`} className="font-semibold text-[var(--primary)]">{item.ticker}</Link></td>
      <td className="font-medium">{item.name}</td>
      <td>{item.composite_score != null ? <span className="pill">{Math.round(item.composite_score)}/100 · {signalName(item.signal_label ?? "")}</span> : <span className="text-[var(--text-muted)]">Sinyal yok</span>}</td>
      <td><Link href={`/piyasalar/${item.ticker}`} className="text-[var(--text-muted)]"><Icon name="chevron" size={16}/></Link></td>
    </tr>)}
  </tbody></table></div>;
}
