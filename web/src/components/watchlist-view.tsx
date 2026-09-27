"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { MarketFeedItem } from "@/lib/types";
import { signalName } from "@/lib/format";
import { EmptyState } from "@/components/ui";
import { Icon } from "@/components/icon";
import { WatchlistStar } from "@/components/watchlist-star";
import { useWatchlist } from "@/lib/watchlist";
import { fetchMarketFeed } from "@/lib/market-feed";

export function WatchlistView() {
  const { tickers } = useWatchlist();
  const [items, setItems] = useState<MarketFeedItem[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    if (!tickers.length) { setItems([]); setLoadError(false); return; }
    const controller = new AbortController();
    setItems(null);
    setLoadError(false);
    fetchMarketFeed(controller.signal)
      .then(setItems)
      .catch((error: unknown) => {
        if (error instanceof Error && error.name === "AbortError") return;
        setItems([]);
        setLoadError(true);
      });
    return () => controller.abort();
  }, [reloadVersion, tickers.length]);

  const watched = (items ?? []).filter((item) => tickers.includes(item.ticker));
  const missing = tickers.filter((ticker) => !(items ?? []).some((item) => item.ticker === ticker));

  if (!tickers.length) return <div className="panel-flat"><EmptyState title="İzleme listeniz boş" description="Piyasalar sayfasında veya bir hisse detayında yıldıza tıklayarak buraya ekleyin."/></div>;
  if (items == null) return <p className="text-sm text-[var(--text-muted)]">Yükleniyor...</p>;
  if (loadError) return <div className="panel-flat grid min-h-56 place-items-center p-8 text-center"><div><p className="text-sm font-medium">İzleme listesi yüklenemedi</p><p className="mt-1 text-xs text-[var(--text-muted)]">Piyasa veri servisine şu anda ulaşılamıyor.</p><button type="button" onClick={() => setReloadVersion((value) => value + 1)} className="mt-4 rounded-md border px-3 py-1.5 text-xs" style={{ borderColor: "var(--border)" }}>Tekrar dene</button></div></div>;

  if (!watched.length) return <div className="panel-flat p-8 text-center"><p className="text-sm font-medium">İzlenen hisseler aktif piyasa evreninde bulunamadı</p><p className="mt-1 text-xs text-[var(--text-muted)]">Eski kayıtları aşağıdaki yıldızlarla listenizden çıkarabilirsiniz.</p><div className="mt-4 flex flex-wrap justify-center gap-2">{missing.map((ticker) => <span key={ticker} className="pill gap-1"><WatchlistStar ticker={ticker} size={14}/>{ticker}</span>)}</div></div>;

  return <>{missing.length > 0 && <div className="mb-3 rounded border px-4 py-3 text-xs text-[var(--warning)]" style={{ borderColor: "color-mix(in srgb, var(--warning) 25%, transparent)", background: "var(--warning-soft)" }}>{missing.join(", ")} aktif piyasa evreninde bulunamadı.</div>}<div className="table-shell overflow-x-auto"><table className="data-table min-w-[560px]"><thead><tr><th className="w-10"><span className="sr-only">İşlem</span></th><th>Hisse</th><th>Şirket</th><th>Bileşik skor</th><th className="w-10"><span className="sr-only">İşlem</span></th></tr></thead><tbody>
    {watched.map((item) => <tr key={item.ticker}>
      <td><WatchlistStar ticker={item.ticker} size={16}/></td>
      <td><Link href={`/piyasalar/${item.ticker}`} className="terminal-mono font-semibold text-[var(--primary)]">{item.ticker}</Link></td>
      <td className="font-medium">{item.name}</td>
      <td>{item.composite_score != null ? <span className="pill">{Math.round(item.composite_score)}/100 · {signalName(item.signal_label ?? "")}</span> : <span className="text-[var(--text-muted)]">Sinyal yok</span>}</td>
      <td><Link href={`/piyasalar/${item.ticker}`} aria-label={`${item.ticker} detayını aç`} className="text-[var(--text-muted)]"><Icon name="chevron" size={16}/></Link></td>
    </tr>)}
  </tbody></table></div></>;
}
