import { DataMetric as Metric } from "@/components/ui";
import type { Metadata } from "next";
import { apiGet } from "@/lib/api";
import type { FundFlow } from "@/lib/types";
import { formatDate, formatMoney, formatPercent } from "@/lib/format";
import { EmptyState, PageHeader, ServiceNotice } from "@/components/ui";
import { Icon } from "@/components/icon";

export const metadata: Metadata = { title: "Kurumsal Veriler" };

export default async function InstitutionalPage() {
  // TEFAS fon akımı günde bir kez toplanıyor.
  const result = await apiGet<FundFlow[]>("/api/funds/flows?limit=90", [], { revalidate: 300 }); const latest = result.data[0];
  const totalFlow = result.data.reduce((sum, item) => sum + (item.total_net_flow ?? 0), 0); const stockFlow = result.data.reduce((sum, item) => sum + (item.estimated_stock_flow ?? 0), 0);
  return <><PageHeader eyebrow="TEFAS fon verileri" title="Kurumsal Veriler" description="TEFAS'taki yatırım fonlarına giren-çıkan paranın ve bu paranın hisse senetlerine düşen tahmini payının günlük takibi."/><ServiceNotice show={!result.ok}/><div className="mb-6 grid grid-cols-2 gap-3 xl:grid-cols-4"><Metric label="Takip edilen fon" value={latest ? String(latest.fund_count) : "—"} icon="building"/><Metric label="Toplam varlık" value={formatMoney(latest?.total_aum, true)} icon="funds"/><Metric label="90 gün net fon akımı" value={formatMoney(totalFlow, true)} tone={totalFlow >= 0} icon="trend"/><Metric label="90 gün tahmini hisse akımı" value={formatMoney(stockFlow, true)} tone={stockFlow >= 0} icon="markets"/></div>
    <div className="panel-flat overflow-hidden"><div className="flex items-center justify-between gap-3 border-b p-4 sm:p-5" style={{ borderColor: "var(--border)" }}><div><h2 className="text-base font-semibold">Günlük fon akımları</h2><p className="mt-1 text-xs text-[var(--text-muted)]">TEFAS yatırım fonları · tahmini değerler</p></div><span className="pill pill-primary shrink-0" title="YAT: TEFAS'ın yatırım fonu kategorisi (emeklilik fonları hariç)">YAT · Yatırım fonu</span></div>{result.data.length ? <div className="overflow-x-auto"><table className="data-table min-w-[760px]"><thead><tr><th>Tarih</th><th>Fon sayısı</th><th>Toplam varlık</th><th>Net fon akımı</th><th title="Net akımın fonların hisse ağırlığıyla çarpılmasıyla bulunan tahmini hisse alım/satımı">Tahmini hisse akımı</th><th title="Gün içinde net para girişi olan fonların oranı">Girişli fon oranı</th></tr></thead><tbody>{result.data.map((item) => <tr key={item.date}><td className="font-medium">{formatDate(item.date)}</td><td>{item.fund_count}</td><td>{formatMoney(item.total_aum, true)}</td><td className={(item.total_net_flow ?? 0) >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"}>{formatMoney(item.total_net_flow, true)}</td><td className={(item.estimated_stock_flow ?? 0) >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"}>{formatMoney(item.estimated_stock_flow, true)}</td><td>{formatPercent(item.positive_flow_pct)}</td></tr>)}</tbody></table></div> : <EmptyState/>}</div><p className="mt-4 text-[11px] leading-5 text-[var(--text-muted)]">Net fon akımı, fonların portföy büyüklüğündeki değişimden fiyat etkisi çıkarılarak tahmin edilir. Tahmini hisse akımı bu akımın fonların varlık dağılımındaki hisse payıyla çarpılmasıdır. İkisi de türetilmiş göstergelerdir; gerçekleşmiş alım-satım verisi değildir.</p></>;
}
