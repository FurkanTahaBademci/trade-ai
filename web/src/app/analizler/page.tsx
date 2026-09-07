import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { Evaluation } from "@/lib/types";
import { PageHeader, ServiceNotice } from "@/components/ui";
import { InfiniteAnalysisFeed } from "@/components/infinite-analysis-feed";

export const metadata: Metadata = { title: "AI Analizleri" };

export default async function AnalysesPage({ searchParams }: { searchParams: Promise<{ source?: "news" | "kap" }> }) {
  const { source } = await searchParams; const query = source ? `&source_type=${source}` : "";
  const result = await apiGet<Evaluation[]>(`/api/evaluations?limit=12${query}`, []);
  return <><PageHeader eyebrow="Gemini değerlendirmeleri" title="AI Analizleri" description="Haber ve KAP içeriklerinin önem, duygu ve etki açısından yapılandırılmış değerlendirmeleri." actions={<div className="flex gap-2"><Filter href="/analizler" active={!source}>Tümü</Filter><Filter href="/analizler?source=news" active={source === "news"}>Haber</Filter><Filter href="/analizler?source=kap" active={source === "kap"}>KAP</Filter></div>}/><ServiceNotice show={!result.ok}/>
    <InfiniteAnalysisFeed key={source ?? "all"} initialItems={result.data} source={source}/>
  </>;
}
function Filter({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) { return <Link href={href} className={`pill transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{children}</Link>; }
