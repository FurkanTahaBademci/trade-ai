import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { Evaluation, SystemStats } from "@/lib/types";
import { PageHeader, ServiceNotice } from "@/components/ui";
import { InfiniteAnalysisFeed } from "@/components/infinite-analysis-feed";
import { TickerFilter, tickerParam } from "@/components/ticker-filter";

export const metadata: Metadata = { title: "AI Analizleri" };

export default async function AnalysesPage({ searchParams }: { searchParams: Promise<{ source?: string; hisse?: string }> }) {
  const params = await searchParams; const source = params.source === "news" || params.source === "kap" ? params.source : undefined; const ticker = tickerParam(params.hisse);
  const query = `${source ? `&source_type=${source}` : ""}${ticker ? `&ticker=${ticker}` : ""}`;
  const filterHref = (value?: "news" | "kap") => { const next = new URLSearchParams(); if (value) next.set("source", value); if (ticker) next.set("hisse", ticker); const text = next.toString(); return text ? `/analizler?${text}` : "/analizler"; };
  const [result, statsRes] = await Promise.all([
    apiGet<Evaluation[]>(`/api/evaluations?limit=12${query}`, []),
    apiGet<SystemStats | null>("/api/system/stats", null, { revalidate: 60 }),
  ]);
  const stats = statsRes.data;
  const total = stats?.evaluations_total;
  const newsCount = stats?.evaluations_by_source?.["news"];
  const kapCount = stats?.evaluations_by_source?.["kap"];

  return <><PageHeader eyebrow="Gemini değerlendirmeleri" title="AI Analizleri" description="Haber ve KAP içeriklerinin önem, duygu ve etki açısından yapılandırılmış değerlendirmeleri." actions={<div className="flex flex-wrap items-center gap-2">{total ? <span className="pill pill-positive mr-1"><span className="h-1.5 w-1.5 rounded-full bg-[var(--positive)]"/>{total.toLocaleString("tr-TR")} analiz</span> : null}<Filter href={filterHref()} active={!source}>Tümü{total ? ` (${total.toLocaleString("tr-TR")})` : ""}</Filter><Filter href={filterHref("news")} active={source === "news"}>Haber{newsCount != null ? ` (${newsCount.toLocaleString("tr-TR")})` : ""}</Filter><Filter href={filterHref("kap")} active={source === "kap"}>KAP{kapCount != null ? ` (${kapCount.toLocaleString("tr-TR")})` : ""}</Filter></div>}/><TickerFilter action="/analizler" ticker={ticker} keep={{ source }}/><ServiceNotice show={!result.ok}/>
    <InfiniteAnalysisFeed key={`${source ?? "all"}-${ticker ?? "all"}`} initialItems={result.data} source={source} ticker={ticker}/>
  </>;
}
function Filter({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) { return <Link href={href} className={`pill transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{children}</Link>; }

