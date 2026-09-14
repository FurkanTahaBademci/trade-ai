import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { Evaluation, SystemStats } from "@/lib/types";
import { PageHeader, ServiceNotice } from "@/components/ui";
import { InfiniteAnalysisFeed } from "@/components/infinite-analysis-feed";

export const metadata: Metadata = { title: "AI Analizleri" };

export default async function AnalysesPage({ searchParams }: { searchParams: Promise<{ source?: "news" | "kap" }> }) {
  const { source } = await searchParams; const query = source ? `&source_type=${source}` : "";
  const [result, statsRes] = await Promise.all([
    apiGet<Evaluation[]>(`/api/evaluations?limit=12${query}`, []),
    apiGet<SystemStats | null>("/api/system/stats", null, { revalidate: 60 }),
  ]);
  const stats = statsRes.data;
  const total = stats?.evaluations_total;
  const newsCount = stats?.evaluations_by_source?.["news"];
  const kapCount = stats?.evaluations_by_source?.["kap"];

  return <><PageHeader eyebrow="Gemini değerlendirmeleri" title="AI Analizleri" description="Haber ve KAP içeriklerinin önem, duygu ve etki açısından yapılandırılmış değerlendirmeleri." actions={<div className="flex flex-wrap items-center gap-2">{total ? <span className="pill pill-positive mr-1"><span className="h-1.5 w-1.5 rounded-full bg-[var(--positive)]"/>{total.toLocaleString("tr-TR")} analiz</span> : null}<Filter href="/analizler" active={!source}>Tümü{total ? ` (${total.toLocaleString("tr-TR")})` : ""}</Filter><Filter href="/analizler?source=news" active={source === "news"}>Haber{newsCount != null ? ` (${newsCount.toLocaleString("tr-TR")})` : ""}</Filter><Filter href="/analizler?source=kap" active={source === "kap"}>KAP{kapCount != null ? ` (${kapCount.toLocaleString("tr-TR")})` : ""}</Filter></div>}/><ServiceNotice show={!result.ok}/>
    <InfiniteAnalysisFeed key={source ?? "all"} initialItems={result.data} source={source}/>
  </>;
}
function Filter({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) { return <Link href={href} className={`pill transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{children}</Link>; }

