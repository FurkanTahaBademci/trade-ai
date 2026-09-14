import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { NewsArticle, SystemStats } from "@/lib/types";
import { sourceName } from "@/lib/format";
import { PageHeader, ServiceNotice } from "@/components/ui";
import { InfiniteNewsFeed } from "@/components/infinite-news-feed";

export const metadata: Metadata = { title: "Haber Akışı" };

const NEWS_SOURCES = ["bloomberght", "investing_tr", "aa_ekonomi", "dunya", "foreks", "trthaber"];

export default async function NewsPage({ searchParams }: { searchParams: Promise<{ source?: string }> }) {
  const { source } = await searchParams; const query = source ? `&source=${encodeURIComponent(source)}` : "";
  const [news, statsRes] = await Promise.all([
    apiGet<NewsArticle[]>(`/api/news?limit=12${query}`, []),
    apiGet<SystemStats | null>("/api/system/stats", null, { revalidate: 60 }),
  ]);
  const stats = statsRes.data;
  const total = stats?.news_total;

  return <><PageHeader eyebrow="Piyasa istihbaratı" title="Haber Akışı" description="Güvenilir finans kaynaklarından toplanan, BIST şirketleriyle otomatik eşleştirilmiş güncel haberler." actions={<div className="flex flex-wrap items-center gap-2">{total ? <span className="pill pill-positive mr-1"><span className="h-1.5 w-1.5 rounded-full bg-[var(--positive)]"/>{total.toLocaleString("tr-TR")} haber</span> : null}<Filter href="/haberler" active={!source}>Tümü{total ? ` (${total.toLocaleString("tr-TR")})` : ""}</Filter>{NEWS_SOURCES.map((name) => { const count = stats?.news_by_source?.[name]; return <Filter key={name} href={`/haberler?source=${name}`} active={source === name}>{sourceName(name)}{count != null ? ` (${count.toLocaleString("tr-TR")})` : ""}</Filter>; })}</div>}/><ServiceNotice show={!news.ok}/>
    <InfiniteNewsFeed key={source ?? "all"} initialItems={news.data} source={source}/>
  </>;
}

function Filter({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) { return <Link href={href} className={`pill transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{children}</Link>; }

