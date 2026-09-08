import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { NewsArticle } from "@/lib/types";
import { sourceName } from "@/lib/format";
import { PageHeader, ServiceNotice } from "@/components/ui";
import { InfiniteNewsFeed } from "@/components/infinite-news-feed";

export const metadata: Metadata = { title: "Haber Akışı" };

const NEWS_SOURCES = ["bloomberght", "investing_tr", "aa_ekonomi", "dunya", "foreks"];

export default async function NewsPage({ searchParams }: { searchParams: Promise<{ source?: string }> }) {
  const { source } = await searchParams; const query = source ? `&source=${encodeURIComponent(source)}` : "";
  const news = await apiGet<NewsArticle[]>(`/api/news?limit=12${query}`, []);
  return <><PageHeader eyebrow="Piyasa istihbaratı" title="Haber Akışı" description="Güvenilir finans kaynaklarından toplanan, BIST şirketleriyle otomatik eşleştirilmiş güncel haberler." actions={<div className="flex flex-wrap gap-2"><Filter href="/haberler" active={!source}>Tümü</Filter>{NEWS_SOURCES.map((name) => <Filter key={name} href={`/haberler?source=${name}`} active={source === name}>{sourceName(name)}</Filter>)}</div>}/><ServiceNotice show={!news.ok}/>
    <InfiniteNewsFeed key={source ?? "all"} initialItems={news.data} source={source}/>
  </>;
}

function Filter({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) { return <Link href={href} className={`pill transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{children}</Link>; }
