import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { CompositeSignal } from "@/lib/types";
import { componentName, formatDate, formatPercent, signalName } from "@/lib/format";
import { EmptyState, PageHeader, ScoreRing, ServiceNotice } from "@/components/ui";
import { PaginatedItems } from "@/components/pagination";
import { Icon } from "@/components/icon";

export const metadata: Metadata = { title: "Bileşik Sinyaller" };

export default async function SignalsPage({ searchParams }: { searchParams: Promise<{ label?: string }> }) {
  const { label } = await searchParams; const query = label ? `&label=${encodeURIComponent(label)}` : "";
  const result = await apiGet<CompositeSignal[]>(`/api/signals?limit=500${query}`, []);
  return <><PageHeader eyebrow="Sürüm v1 · Teknik sıralama" title="Bileşik Sinyaller" description="AI etkisi, temel analiz, analist konsensüsü ve fon akımının açıklanabilir 0–100 bileşik görünümü." actions={<div className="flex flex-wrap gap-2"><Filter href="/sinyaller" active={!label}>Tümü</Filter><Filter href="/sinyaller?label=VERY_POSITIVE" active={label === "VERY_POSITIVE"}>Çok pozitif</Filter><Filter href="/sinyaller?label=POSITIVE" active={label === "POSITIVE"}>Pozitif</Filter><Filter href="/sinyaller?label=NEUTRAL" active={label === "NEUTRAL"}>Nötr</Filter></div>}/><ServiceNotice show={!result.ok}/>
    <div className="mb-5 flex items-center gap-3 rounded-[12px] border px-4 py-3 text-xs text-[var(--text-secondary)]" style={{ borderColor: "var(--border)", background: "var(--surface)" }}><Icon name="activity" size={15} className="text-[var(--primary)]"/><strong className="text-[var(--text)]">{result.data.length}</strong> hisse sıralandı <span className="text-[var(--border-strong)]">•</span> Eksik bileşenler sıfır sayılmaz; ağırlıklar mevcut veriye göre normalize edilir.</div>
    {result.data.length ? <PaginatedItems pageSize={15} items={result.data.map((item, index) => <Link href={`/piyasalar/${item.ticker}`} key={item.id} className="panel-flat group grid gap-4 p-4 transition hover:border-[var(--border-strong)] sm:grid-cols-[42px_72px_130px_minmax(240px,1fr)_130px_20px] sm:items-center sm:p-5"><span className="text-center text-xs font-semibold text-[var(--text-muted)]">#{index + 1}</span><ScoreRing score={item.composite_score} label="Skor" size={62}/><div><p className="text-base font-semibold text-[var(--primary)]">{item.ticker}</p><p className="mt-1 text-[11px] text-[var(--text-muted)]">{formatDate(item.as_of_date)}</p></div><div className="grid grid-cols-2 gap-x-5 gap-y-2">{Object.entries(item.component_scores).map(([name, score]) => <div key={name}><div className="mb-1 flex justify-between text-[10px] text-[var(--text-muted)]"><span>{componentName(name)}</span><span>{Math.round(score)}</span></div><div className="h-1 rounded-full bg-[var(--border)]"><div className="h-1 rounded-full bg-[var(--primary)]" style={{ width: `${score}%` }}/></div></div>)}</div><div><span className={`pill ${item.signal_label.includes("POSITIVE") ? "pill-positive" : item.signal_label.includes("NEGATIVE") ? "pill-negative" : ""}`}>{signalName(item.signal_label)}</span><p className="mt-2 text-[11px] text-[var(--text-muted)]">Güven {formatPercent(item.confidence * 100)}</p></div><Icon name="chevron" size={16} className="hidden text-[var(--text-muted)] sm:block"/></Link>)}/> : <div className="panel-flat"><EmptyState title="Bileşik skor henüz yok" description="Sinyal motoru ilk kez çalıştığında en az iki veri bileşeni bulunan hisseler burada sıralanacak."/></div>}
    <p className="mt-5 text-[11px] leading-5 text-[var(--text-muted)]">Bu skor teknik bir araştırma ve sıralama göstergesidir; yatırım tavsiyesi veya otomatik al-sat emri değildir.</p></>;
}

function Filter({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) { return <Link href={href} className={`pill transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{children}</Link>; }
