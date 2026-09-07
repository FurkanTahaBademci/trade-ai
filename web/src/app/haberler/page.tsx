import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { NewsArticle } from "@/lib/types";
import { formatDate, sourceName } from "@/lib/format";
import { EmptyState, PageHeader, ServiceNotice, TickerPills } from "@/components/ui";
import { Icon } from "@/components/icon";
import { PaginatedItems } from "@/components/pagination";

export const metadata: Metadata = { title: "Haber Akışı" };

export default async function NewsPage({ searchParams }: { searchParams: Promise<{ source?: string }> }) {
  const { source } = await searchParams; const query = source ? `&source=${encodeURIComponent(source)}` : "";
  const news = await apiGet<NewsArticle[]>(`/api/news?limit=100${query}`, []);
  return <><PageHeader eyebrow="Piyasa istihbaratı" title="Haber Akışı" description="Güvenilir finans kaynaklarından toplanan, BIST şirketleriyle otomatik eşleştirilmiş güncel haberler." actions={<div className="flex gap-2"><Filter href="/haberler" active={!source}>Tümü</Filter><Filter href="/haberler?source=bloomberght" active={source === "bloomberght"}>Bloomberg HT</Filter><Filter href="/haberler?source=investing_tr" active={source === "investing_tr"}>Investing</Filter></div>}/><ServiceNotice show={!news.ok}/>
    {news.data.length ? <PaginatedItems pageSize={12} className="grid gap-3 lg:grid-cols-2" items={news.data.map((item) => <article key={item.id} className="panel-flat group flex flex-col p-5 transition hover:-translate-y-0.5 hover:border-[var(--border-strong)]"><div className="mb-4 flex items-center justify-between"><span className="eyebrow">{sourceName(item.source)}</span><span className="flex items-center gap-1 text-[11px] text-[var(--text-muted)]"><Icon name="clock" size={12}/>{formatDate(item.published_at, true)}</span></div><Link href={`/haberler/${item.id}`}><h2 className="text-base font-semibold leading-6 tracking-[-0.018em] group-hover:text-[var(--primary)]">{item.title}</h2></Link>{item.summary && <p className="mt-2 line-clamp-3 text-sm leading-6 text-[var(--text-secondary)]">{item.summary}</p>}<div className="mt-auto flex items-end justify-between gap-4 pt-5"><TickerPills tickers={item.ticker_codes}/><Link href={`/haberler/${item.id}`} className="flex shrink-0 items-center gap-1 text-xs font-medium text-[var(--primary)]">Detay <Icon name="arrow" size={13}/></Link></div></article>)}/> : <div className="panel-flat"><EmptyState/></div>}
  </>;
}

function Filter({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) { return <Link href={href} className={`pill transition ${active ? "pill-primary" : "hover:text-[var(--text)]"}`}>{children}</Link>; }
