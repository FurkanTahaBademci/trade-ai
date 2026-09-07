import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { Evaluation } from "@/lib/types";
import { eventName, formatDate, formatPercent, sourceName } from "@/lib/format";
import { EmptyState, PageHeader, ScoreRing, ServiceNotice, TickerPills } from "@/components/ui";
import { Icon } from "@/components/icon";
import { PaginatedItems } from "@/components/pagination";

export const metadata: Metadata = { title: "AI Analizleri" };

export default async function AnalysesPage({ searchParams }: { searchParams: Promise<{ source?: "news" | "kap" }> }) {
  const { source } = await searchParams; const query = source ? `&source_type=${source}` : "";
  const result = await apiGet<Evaluation[]>(`/api/evaluations?limit=100${query}`, []);
  const succeeded = result.data.filter((item) => item.status === "succeeded");
  return <><PageHeader eyebrow="Gemini değerlendirmeleri" title="AI Analizleri" description="Haber ve KAP içeriklerinin önem, duygu ve etki açısından yapılandırılmış değerlendirmeleri." actions={<div className="flex gap-2"><Filter href="/analizler" active={!source}>Tümü</Filter><Filter href="/analizler?source=news" active={source === "news"}>Haber</Filter><Filter href="/analizler?source=kap" active={source === "kap"}>KAP</Filter></div>}/><ServiceNotice show={!result.ok}/>
    <div className="mb-5 flex flex-wrap items-center gap-3 rounded-[12px] border px-4 py-3 text-xs text-[var(--text-secondary)]" style={{ borderColor: "var(--border)", background: "var(--surface)" }}><Icon name="spark" size={15} className="text-[var(--primary)]"/><strong className="text-[var(--text)]">{succeeded.length}</strong> başarılı değerlendirme <span className="text-[var(--border-strong)]">•</span> Skorlar yatırım tavsiyesi değildir.</div>
    {result.data.length ? <PaginatedItems pageSize={12} items={result.data.map((item) => <Link href={`/analizler/${item.id}`} key={item.id} className="panel-flat group grid gap-4 p-4 transition hover:border-[var(--border-strong)] sm:grid-cols-[82px_minmax(0,1fr)_140px_24px] sm:items-center sm:p-5"><ScoreRing score={item.impact_score} label="Etki" size={68}/><div className="min-w-0"><div className="mb-2 flex flex-wrap items-center gap-2"><span className="pill">{sourceName(item.source_type)}</span><span className="pill pill-primary">{eventName(item.event_type)}</span><span className={`pill ${item.status === "succeeded" ? "pill-positive" : item.status === "failed" ? "pill-negative" : ""}`}>{item.status === "succeeded" ? "Tamamlandı" : item.status === "failed" ? "Hata" : "İşleniyor"}</span></div><h2 className="line-clamp-2 text-sm font-medium leading-5 group-hover:text-[var(--primary)]">{item.summary || item.error_text || "Değerlendirme işleniyor"}</h2><div className="mt-2"><TickerPills tickers={item.ticker_codes}/></div></div><div className="text-xs text-[var(--text-muted)]"><p>{formatDate(item.created_at, true)}</p><p className="mt-1">Güven {formatPercent((item.confidence ?? 0) * 100)}</p><p className="mt-1">Tier {item.tier}</p></div><Icon name="chevron" size={16} className="hidden text-[var(--text-muted)] sm:block"/></Link>)}/> : <div className="panel-flat"><EmptyState title="AI değerlendirmesi yok" description="LLM özelliği etkinleştirildiğinde haber ve KAP analizleri burada görünür."/></div>}
  </>;
}
function Filter({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) { return <Link href={href} className={`pill transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{children}</Link>; }
