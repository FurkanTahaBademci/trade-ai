"use client";

import Link from "next/link";
import { useMemo } from "react";
import type { BacktestTrade } from "@/lib/types";
import { formatDate, formatMoney, formatNumber } from "@/lib/format";
import { useInfiniteFeed } from "@/lib/use-infinite-feed";
import { InfiniteFeedStatus } from "./infinite-feed-status";
import { EmptyState } from "./ui";

const cursorFor = (item: BacktestTrade) => ({ before_id: item.id });
const keyFor = (item: BacktestTrade) => item.id;

export function BacktestTrades({ initialItems, runId, ticker, side }: {
  initialItems: BacktestTrade[]; runId: number; ticker?: string; side?: string;
}) {
  const filters = useMemo(() => ({ ticker, side }), [ticker, side]);
  const feed = useInfiniteFeed({ initialItems, pageSize: 25, endpoint: `/api/backtest-trades/${runId}`, filters, cursorFor, keyFor });
  if (!feed.items.length) return <div className="panel-flat"><EmptyState compact title="İşlem bulunamadı" description={ticker || side ? "Bu filtrelere uyan işlem yok. Filtreleri temizleyerek tekrar deneyin." : "Bu koşuda işlem oluşmadı. Sinyal ve fiyat kapsamını kontrol edin."}/></div>;
  return <div aria-busy={feed.loading}>
    <p className="mb-3 text-xs text-[var(--text-muted)]">{feed.items.length} işlem gösteriliyor · En yeni işlemler önce</p>
    <div className="table-shell overflow-x-auto"><table className="data-table min-w-[760px]">
      <thead><tr><th>Tarih</th><th>Hisse</th><th>Yön</th><th>Adet</th><th>Fiyat</th><th>Tutar</th><th>Komisyon</th><th>Gerç. K/Z</th></tr></thead>
      <tbody>{feed.items.map((trade) => <tr key={trade.id}>
        <td><span className="block">{formatDate(trade.execution_date)}</span><span className="text-[10px] text-[var(--text-muted)]">Sinyal {formatDate(trade.signal_date)}</span></td>
        <td><Link href={`/piyasalar/${trade.ticker}`} className="font-semibold text-[var(--primary)]">{trade.ticker}</Link></td>
        <td><span className={`pill ${trade.side === "BUY" ? "pill-positive" : "pill-negative"}`}>{trade.side === "BUY" ? "Alış" : "Satış"}</span></td>
        <td>{formatNumber(trade.quantity, 0)}</td><td>{formatMoney(trade.price)}</td><td>{formatMoney(trade.gross_amount)}</td><td>{formatMoney(trade.fee_amount)}</td>
        <td className={(trade.realized_pnl ?? 0) >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"}>{formatMoney(trade.realized_pnl)}</td>
      </tr>)}</tbody>
    </table></div>
    <InfiniteFeedStatus {...feed} onRetry={() => void feed.loadMore()} endLabel="Bu filtrelere uyan tüm işlemleri gördünüz."/>
  </div>;
}
