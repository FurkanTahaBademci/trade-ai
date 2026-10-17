import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { Evaluation, SystemStats } from "@/lib/types";
import { PageHeader, ServiceNotice } from "@/components/ui";
import { InfiniteAnalysisFeed } from "@/components/infinite-analysis-feed";
import { TickerFilter, tickerParam } from "@/components/ticker-filter";

export const metadata: Metadata = { title: "AI Analizleri" };

// Etki skoru 0-5 olan rutin içerikler listeyi doldurmasın diye varsayılan bir eşik uygulanır.
const DEFAULT_MIN_IMPACT = 20;
const IMPACT_LEVELS = [20, 50];

/** `?etki=`: "tumu" eşiği kaldırır; tanınmayan değerler varsayılana düşer. */
function minImpactParam(raw: string | undefined) {
  if (raw === "tumu") return undefined;
  const value = Number(raw);
  return IMPACT_LEVELS.includes(value) ? value : DEFAULT_MIN_IMPACT;
}

export default async function AnalysesPage({ searchParams }: { searchParams: Promise<{ source?: string; hisse?: string; etki?: string }> }) {
  const params = await searchParams; const source = params.source === "news" || params.source === "kap" ? params.source : undefined; const ticker = tickerParam(params.hisse);
  const minImpact = minImpactParam(params.etki);
  const query = `${source ? `&source_type=${source}` : ""}${ticker ? `&ticker=${ticker}` : ""}${minImpact != null ? `&min_impact=${minImpact}` : ""}`;
  const hrefFor = (value: "news" | "kap" | undefined, impact: number | undefined) => { const next = new URLSearchParams(); if (value) next.set("source", value); if (ticker) next.set("hisse", ticker); if (impact == null) next.set("etki", "tumu"); else if (impact !== DEFAULT_MIN_IMPACT) next.set("etki", String(impact)); const text = next.toString(); return text ? `/analizler?${text}` : "/analizler"; };
  const filterHref = (value?: "news" | "kap") => hrefFor(value, minImpact);
  const impactHref = (impact?: number) => hrefFor(source, impact);
  const [result, statsRes] = await Promise.all([
    // İlk sayfa 30 sn önbellekli; sonraki sayfalar canlı akıştan gelir ve tekrarlar ayıklanır.
    apiGet<Evaluation[]>(`/api/evaluations?limit=12${query}`, [], { revalidate: 30 }),
    apiGet<SystemStats | null>("/api/system/stats", null, { revalidate: 60 }),
  ]);
  const stats = statsRes.data;
  const total = stats?.evaluations_total;
  const newsCount = stats?.evaluations_by_source?.["news"];
  const kapCount = stats?.evaluations_by_source?.["kap"];

  return <><PageHeader eyebrow="Yapay zekâ değerlendirmeleri" title="AI Analizleri" description="Haber ve KAP içeriklerinin önem, duygu ve fiyat etkisi açısından yapay zekâ ile yapılandırılmış değerlendirmeleri. Etki skoru 0–100 arasıdır; varsayılan olarak etkisi düşük rutin içerikler gizlenir." actions={<div className="-mx-3 flex w-[calc(100%+1.5rem)] items-center gap-2 overflow-x-auto whitespace-nowrap px-3 pb-1 [scrollbar-width:none] sm:mx-0 sm:w-auto sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0"><Filter href={filterHref()} active={!source}>Tümü{total ? ` (${total.toLocaleString("tr-TR")})` : ""}</Filter><Filter href={filterHref("news")} active={source === "news"}>Haber{newsCount != null ? ` (${newsCount.toLocaleString("tr-TR")})` : ""}</Filter><Filter href={filterHref("kap")} active={source === "kap"}>KAP{kapCount != null ? ` (${kapCount.toLocaleString("tr-TR")})` : ""}</Filter></div>}/>
    <div className="mb-3 flex flex-wrap items-center gap-2" role="group" aria-label="Minimum etki skoru"><span className="text-xs text-[var(--text-muted)]" title="0–100 arası tahmini fiyat etkisi">Minimum etki:</span>{IMPACT_LEVELS.map((level) => <Filter key={level} href={impactHref(level)} active={minImpact === level}>≥ {level}</Filter>)}<Filter href={impactHref(undefined)} active={minImpact == null}>Tümünü göster</Filter></div>
    <TickerFilter action="/analizler" ticker={ticker} keep={{ source, etki: minImpact == null ? "tumu" : minImpact !== DEFAULT_MIN_IMPACT ? String(minImpact) : undefined }}/><ServiceNotice show={!result.ok}/>
    <InfiniteAnalysisFeed key={`${source ?? "all"}-${ticker ?? "all"}-${minImpact ?? "all"}`} initialItems={result.data} source={source} ticker={ticker} minImpact={minImpact}/>
  </>;
}
function Filter({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) { return <Link prefetch={false} href={href} aria-current={active ? "true" : undefined} className={`pill shrink-0 transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{children}</Link>; }
