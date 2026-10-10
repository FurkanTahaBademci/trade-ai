import { DataMetric as Metric } from "@/components/ui";
import type { Metadata } from "next";
import { apiGet } from "@/lib/api";
import type { MacroSeries, MonetaryPolicyDecision } from "@/lib/types";
import { formatDate, formatNumber, formatPercent } from "@/lib/format";
import { EmptyState, PageHeader, ServiceNotice, SectionTitle } from "@/components/ui";
import { Icon } from "@/components/icon";

export const metadata: Metadata = { title: "Faiz ve Makro" };

const decisionText = { HIKE: "Faiz artırımı", CUT: "Faiz indirimi", HOLD: "Faiz sabit", SCHEDULED: "Toplantı planlandı" };

export default async function MacroPage() {
  const [result, series] = await Promise.all([
    apiGet<MonetaryPolicyDecision[]>("/api/macro/policy-decisions?limit=40", []),
    apiGet<MacroSeries[]>("/api/macro/series", [], { revalidate: 600 }),
  ]);
  const published = result.data.filter((item) => item.status === "PUBLISHED");
  const scheduled = result.data.filter((item) => item.status === "SCHEDULED").sort((a, b) => a.decision_date.localeCompare(b.decision_date));
  const latest = published[0]; const next = scheduled.find((item) => new Date(item.decision_date).getTime() >= Date.now());
  return <><PageHeader eyebrow="Türkiye · Para politikası" title="Faiz ve Piyasa Etkisi" description="Resmî TCMB PPK kararları, yaklaşan toplantılar ve kararların temel aktarım kanallarına göre senaryo bazlı piyasa etkisi." actions={latest?.source_url && <a href={latest.source_url} target="_blank" rel="noreferrer" className="pill pill-primary">Resmî kararı aç <Icon name="external" size={12}/></a>}/><ServiceNotice show={!result.ok}/>
    {series.data.length > 0 && <section className="mb-6"><SectionTitle title="Piyasa göstergeleri" subtitle="TCMB EVDS · gösterge kurları ve TÜFE"/><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{series.data.map((item) => <MacroCard key={item.code} item={item}/>)}</div></section>}
    {latest ? <><div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Politika faizi" value={`%${formatNumber(latest.policy_rate, 2)}`} meta={decisionText[latest.decision_type]}/><Metric label="Son değişim" value={latest.change_bps == null ? "—" : `${latest.change_bps > 0 ? "+" : ""}${latest.change_bps} bp`} meta={formatDate(latest.decision_date)}/><Metric label="Faiz koridoru" value={`%${formatNumber(latest.borrowing_rate, 2)} — %${formatNumber(latest.lending_rate, 2)}`} meta="Borçlanma / borç verme"/><Metric label="Sonraki toplantı" value={next ? formatDate(next.decision_date) : "Takvim bekleniyor"} meta="PPK karar tarihi"/></div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(340px,.75fr)]"><div className="space-y-4"><section className="panel p-5 sm:p-4"><div className="mb-4 flex flex-wrap items-center gap-2"><span className={`pill ${latest.decision_type === "CUT" ? "pill-positive" : latest.decision_type === "HIKE" ? "pill-negative" : "pill-primary"}`}>{decisionText[latest.decision_type]}</span><span className="text-[11px] text-[var(--text-muted)]">{latest.decision_no} · {formatDate(latest.decision_date)}</span></div><h2 className="text-lg font-semibold">TCMB karar özeti</h2><p className="mt-3 text-sm leading-7 text-[var(--text-secondary)]">{latest.summary}</p>{latest.guidance && <div className="mt-4 rounded border p-4 text-xs leading-6 text-[var(--text-secondary)]" style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}><span className="eyebrow mb-2 block">İleriye dönük yönlendirme</span>{latest.guidance}</div>}</section>
        <section><SectionTitle title="Piyasa aktarım kanalları" subtitle={`${latest.market_impact.overall} · kural tabanlı senaryo`}/><div className="grid gap-3 sm:grid-cols-2"><Impact title="BIST şirketleri" text={latest.market_impact.equities}/><Impact title="Bankalar" text={latest.market_impact.banks}/><Impact title="Gayrimenkul" text={latest.market_impact.real_estate}/><Impact title="Türk lirası" text={latest.market_impact.try}/><Impact title="Tahvil piyasası" text={latest.market_impact.bonds}/></div><p className="mt-3 text-[11px] leading-5 text-[var(--text-muted)]">{latest.market_impact.disclaimer} Kararın piyasa beklentisinden sapması ve metnin tonu gerçekleşen yönü değiştirebilir.</p></section></div>
        <aside><SectionTitle title="Karar geçmişi" subtitle={`${published.length} yayımlanmış karar`}/><div className="panel-flat overflow-hidden">{published.map((item, index) => <div key={item.id} className={`p-4 ${index ? "border-t" : ""}`} style={{ borderColor: "var(--border)" }}><div className="flex items-center gap-3"><span className={`grid h-8 w-8 place-items-center rounded ${item.decision_type === "CUT" ? "bg-[var(--positive-soft)] text-[var(--positive)]" : item.decision_type === "HIKE" ? "bg-[var(--negative-soft)] text-[var(--negative)]" : "bg-[var(--primary-soft)] text-[var(--primary)]"}`}><Icon name="trend" size={15} className={item.decision_type === "CUT" ? "rotate-180" : ""}/></span><div><p className="text-sm font-semibold">%{formatNumber(item.policy_rate, 2)}</p><p className="text-[10px] text-[var(--text-muted)]">{formatDate(item.decision_date)}</p></div><div className="ml-auto text-right"><p className="text-xs font-medium">{decisionText[item.decision_type]}</p><p className="mt-0.5 text-[10px] text-[var(--text-muted)]">{item.change_bps == null ? "—" : `${item.change_bps > 0 ? "+" : ""}${item.change_bps} bp`}</p></div></div></div>)}</div>{scheduled.length > 0 && <><SectionTitle title="Yaklaşan toplantılar" subtitle="Resmî TCMB takvimi"/><div className="panel-flat overflow-hidden">{scheduled.map((item, index) => <div key={item.id} className={`flex items-center gap-3 p-4 ${index ? "border-t" : ""}`} style={{ borderColor: "var(--border)" }}><Icon name="clock" size={15} className="text-[var(--primary)]"/><span className="text-sm font-medium">{formatDate(item.decision_date)}</span><span className="ml-auto pill">Planlandı</span></div>)}</div></>}</aside></div></> : <div className="panel-flat"><EmptyState title="TCMB kararları henüz toplanmadı" description="Collector ilk çalıştığında resmî PPK kararları ve toplantı takvimi burada görünecek."/></div>}
  </>;
}

function Impact({ title, text }: { title: string; text: string }) { return <div className="panel-flat p-4"><p className="text-sm font-semibold">{title}</p><p className="mt-2 text-xs leading-5 text-[var(--text-muted)]">{text}</p></div>; }

function MacroCard({ item }: { item: MacroSeries }) {
  const monthly = item.yoy_pct != null;
  const meta = monthly
    ? `Yıllık ${formatPercent(item.yoy_pct, true)} · aylık ${formatPercent(item.change_pct, true)}`
    : `Önceki güne göre ${formatPercent(item.change_pct, true)}`;
  return <Metric label={item.label} value={item.latest_value == null ? "—" : formatNumber(item.latest_value, monthly ? 2 : 4)} meta={`${meta}${item.latest_date ? ` · ${formatDate(item.latest_date)}` : ""}`}/>;
}
