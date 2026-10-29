import Link from "next/link";
import type { IndexPrice, PaperPortfolio, PaperPosition, PaperRisk, PaperSnapshot, PaperTrade } from "@/lib/types";
import { formatDate, formatMoney, formatNumber, formatPercent } from "@/lib/format";
import { DataMetric as Metric, EmptyState, SectionTitle } from "./ui";
import { EquityChart } from "./equity-chart";
import { Icon } from "./icon";

const EXIT_LABELS: Record<string, string> = { stop_loss: "Zarar-kes", take_profit: "Kâr-al", trailing_stop: "Trailing stop", signal: "Sinyal", rebalance: "Rebalance" };

export type PaperPortfolioViewProps = {
  portfolio: PaperPortfolio;
  positions: PaperPosition[];
  trades: PaperTrade[];
  performance: PaperSnapshot[];
  risk: PaperRisk | null;
  indexPrices: IndexPrice[];
  csvHref: string;
  /** Strateji portföyünün en fazla pozisyon sayısı; manuel portföyde boş. */
  positionLimit: number | null;
  /** Risk bölümünün alt başlığındaki kuralların kaynağı. */
  riskNote: string;
};

/** Model portföy ve kullanıcı portföyleri için ortak gösterge paneli. */
export function PaperPortfolioView({ portfolio, positions, trades, performance, risk, indexPrices, csvHref, positionLimit, riskNote }: PaperPortfolioViewProps) {
  // Manuel portföyde tek pozisyon tavanı yoktur (kurallar 0 döner).
  const positionCap = risk?.rules.max_position_weight_pct || null;
  // Tavan alım anında uygulanır; fiyat artışıyla aşılabilir, bu durumda metrik uyarı rengine döner.
  const topOverCap = risk != null && positionCap != null && risk.top_position_weight_pct > positionCap;
  const latest = performance[0]; const relative = relativeToBenchmark(performance, indexPrices);
  const overCap = (ticker: string) => positionCap != null && (latest?.weights[ticker] ?? 0) > positionCap;
  return <>
    <div className="mb-6 grid grid-cols-2 gap-3 xl:grid-cols-5"><div className="col-span-2 grid xl:col-span-1"><Metric label="Toplam değer" value={formatMoney(latest?.total_equity ?? portfolio.initial_cash)} meta={formatPercent(latest?.total_return_pct ?? 0, true)} tone={(latest?.total_return_pct ?? 0) >= 0}/></div><Metric label="Nakit bakiye" value={formatMoney(portfolio.cash_balance)} meta={`%${latest?.total_equity ? formatNumber(portfolio.cash_balance / latest.total_equity * 100) : "100"} nakit`}/><Metric label="Gerçekleşmemiş K/Z" value={formatMoney(latest?.unrealized_pnl ?? 0)} meta={`Gerçekleşen K/Z ${formatMoney(portfolio.realized_pnl)}`} tone={(latest?.unrealized_pnl ?? 0) >= 0}/><Metric label="Toplam komisyon" value={formatMoney(portfolio.total_fees)} meta={`${latest?.position_count ?? positions.length} açık pozisyon`}/><Metric label="BIST100'e göre" value={relative ? formatPercent(relative.excess, true) : "—"} meta={relative ? `Portföy ${formatPercent(relative.portfolio, true)} · BIST100 ${formatPercent(relative.benchmark, true)}` : "En az iki gün sonu değerlemesi gerekir"} tone={relative ? relative.excess >= 0 : undefined}/></div>
    <section className="mb-6"><SectionTitle title="Açık pozisyonlar" subtitle={`${positionLimit ? `${positions.length}/${positionLimit}` : positions.length} pozisyon${positionCap ? ` · tek pozisyon tavanı %${formatNumber(positionCap, 0)}` : ""}`}/>{positions.length ? <div className="table-shell overflow-x-auto"><table className="data-table min-w-[720px]"><thead><tr><th>Hisse</th><th>Adet</th><th>Ort. maliyet</th><th>Son fiyat</th><th>Piyasa değeri</th><th>Açık K/Z</th><th>Ağırlık</th></tr></thead><tbody>{positions.map((item) => { const pnlPct = item.average_cost ? (item.last_price / item.average_cost - 1) * 100 : 0; return <tr key={item.id}><td><Link prefetch={false} href={`/piyasalar/${item.ticker}`} className="font-semibold text-[var(--primary)]">{item.ticker}</Link></td><td>{formatNumber(item.quantity, 0)}</td><td>{formatMoney(item.average_cost)}</td><td>{formatMoney(item.last_price)}</td><td>{formatMoney(item.market_value)}</td><td className={item.unrealized_pnl >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"}>{formatMoney(item.unrealized_pnl)} <span className="text-[10px]">({formatPercent(pnlPct, true)})</span></td><td className={overCap(item.ticker) ? "font-medium text-[var(--warning)]" : undefined} title={overCap(item.ticker) ? "Tek pozisyon tavanının üzerinde" : undefined}>{formatPercent(latest?.weights[item.ticker])}</td></tr>; })}</tbody></table></div> : <div className="panel-flat"><EmptyState compact title="Açık pozisyon yok"/></div>}</section>
    <div className="mb-6 grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(330px,.7fr)]"><div className="min-w-0 space-y-4"><section className="panel-flat p-4"><SectionTitle title="Portföy performansı" subtitle={`${portfolio.strategy_version} · EOD değerleme`}/><EquityChart snapshots={performance} indexPrices={indexPrices}/></section></div>
      <aside><SectionTitle title="Son işlemler" subtitle={`${trades.length} kayıt`}/>{trades.length > 0 && <a href={csvHref} download className="pill mb-3 transition hover:text-[var(--text)]"><Icon name="download" size={12}/>CSV indir</a>}<div className="panel-flat overflow-hidden">{trades.length ? trades.slice(0, 12).map((item, index) => <div key={item.id} className={`p-4 ${index ? "border-t" : ""}`} style={{ borderColor: "var(--border)" }}><div className="flex items-center gap-3"><span className={`grid h-8 w-8 place-items-center rounded ${item.side === "BUY" ? "bg-[var(--positive-soft)] text-[var(--positive)]" : "bg-[var(--negative-soft)] text-[var(--negative)]"}`}><Icon name="arrow" size={14} className={item.side === "SELL" ? "rotate-180" : ""}/></span><div><Link prefetch={false} href={`/piyasalar/${item.ticker}`} className="text-sm font-semibold">{item.ticker}</Link><p className="mt-0.5 text-[10px] text-[var(--text-muted)]">{formatDate(item.trade_date)} · {item.side === "BUY" ? "Alış" : "Satış"}{item.exit_reason && <span className="pill ml-1.5">{EXIT_LABELS[item.exit_reason] ?? item.exit_reason}</span>}</p></div><div className="ml-auto text-right"><p className="text-xs font-medium">{formatMoney(item.gross_amount)}</p><p className="mt-0.5 text-[10px] text-[var(--text-muted)]">{formatNumber(item.quantity, 0)} adet</p>{item.side === "SELL" && item.realized_pnl != null && <p className={`mt-0.5 text-[10px] font-medium ${item.realized_pnl >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"}`}>K/Z {formatMoney(item.realized_pnl)}</p>}</div></div><p className="mt-2 line-clamp-2 text-[10px] leading-4 text-[var(--text-muted)]">{item.reason}</p></div>) : <EmptyState compact title="İşlem henüz yok"/>}</div></aside></div>
    {risk && <section className="mb-6"><SectionTitle title="Risk yönetimi" subtitle={`${risk.observations} günlük gözlem · ${riskNote}`}/><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Maks. drawdown" value={formatPercent(-risk.max_drawdown_pct)} meta="Zirveden en büyük düşüş" tone={risk.max_drawdown_pct < 10 ? "positive" : "negative"}/><Metric label="Volatilite (yıllık)" value={formatPercent(risk.volatility_pct)} meta="Günlük getiri std. sapması"/><Metric label="En büyük pozisyon" value={formatPercent(risk.top_position_weight_pct)} meta={topOverCap && positionCap ? `${risk.top_position_ticker} · %${formatNumber(positionCap, 0)} tavanı alım sonrası fiyat hareketiyle aşıldı${risk.rules.rebalance_enabled ? `; %${formatNumber(positionCap * 1.25, 1)} üstüne çıkarsa yeniden dengelemede kırpılır` : ""}` : risk.top_position_ticker ?? "Pozisyon yok"} tone={topOverCap ? "warning" : risk.top_position_ticker ? "positive" : undefined}/><Metric label="Nakit payı" value={formatPercent(risk.cash_weight_pct)} meta={positionCap ? `Tek pozisyon tavanı %${formatNumber(positionCap, 0)}` : "Tek pozisyon tavanı yok"}/></div>
      <div className="mt-3 grid gap-4 lg:grid-cols-2"><div className="panel-flat p-4"><p className="text-xs font-semibold">Sektör dağılımı</p>{risk.sector_allocation.length ? <ul className="mt-3 space-y-2.5">{risk.sector_allocation.map((row) => <li key={row.sector}><div className="flex items-center justify-between text-[11px]"><span>{row.sector}</span><span className="text-[var(--text-muted)]">{formatPercent(row.weight_pct)} · {formatMoney(row.value)}</span></div><div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--surface-2,var(--border))]" role="img" aria-label={`${row.sector} yüzde ${row.weight_pct}`}><div className="h-full rounded-full bg-[var(--primary)]" style={{ width: `${Math.min(100, row.weight_pct)}%` }}/></div></li>)}</ul> : <EmptyState compact title="Sektör verisi yok"/>}</div>
        {positionCap != null && <div className="panel-flat p-4"><p className="text-xs font-semibold">Aktif risk kuralları</p><dl className="mt-3 grid grid-cols-2 gap-y-2 text-[11px]">{([["Zarar-kes", risk.rules.stop_loss_pct], ["Kâr-al", risk.rules.take_profit_pct], ["Trailing stop", risk.rules.trailing_stop_pct], ["Sektör limiti", risk.rules.max_sector_weight_pct]] as [string, number][]).map(([label, value]) => <div key={label} className="contents"><dt className="text-[var(--text-muted)]">{label}</dt><dd className="text-right font-medium">{value > 0 ? `%${formatNumber(value, 0)}` : "Kapalı"}</dd></div>)}<dt className="text-[var(--text-muted)]">Tek pozisyon tavanı</dt><dd className="text-right font-medium">%{formatNumber(positionCap, 0)}</dd><dt className="text-[var(--text-muted)]">Rebalance</dt><dd className="text-right font-medium">{risk.rules.rebalance_enabled ? "Açık" : "Kapalı"}</dd></dl></div>}</div></section>}
  </>;
}

// İlk gün sonu değerlemesinden bu yana portföy ve BIST100 değişimi (aynı tarih aralığı).
export function relativeToBenchmark(snapshots: PaperSnapshot[], index: IndexPrice[]) {
  const ordered = [...snapshots].sort((a, b) => a.snapshot_date.localeCompare(b.snapshot_date));
  const first = ordered[0]; const last = ordered[ordered.length - 1];
  if (!first || !last || first === last || !first.total_equity) return null;
  const series = [...index].filter((row) => row.value > 0).sort((a, b) => a.date.localeCompare(b.date));
  const start = series.find((row) => row.date >= first.snapshot_date);
  const end = [...series].reverse().find((row) => row.date <= last.snapshot_date);
  if (!start || !end || start.date >= end.date) return null;
  const portfolio = (last.total_equity / first.total_equity - 1) * 100;
  const benchmark = (end.value / start.value - 1) * 100;
  return { portfolio, benchmark, excess: portfolio - benchmark };
}
