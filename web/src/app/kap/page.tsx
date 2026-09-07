import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { Disclosure } from "@/lib/types";
import { formatDate } from "@/lib/format";
import { EmptyState, PageHeader, ServiceNotice, TickerPills } from "@/components/ui";
import { Icon } from "@/components/icon";
import { PaginatedItems } from "@/components/pagination";

export const metadata: Metadata = { title: "KAP Bildirimleri" };

export default async function KapPage() {
  const result = await apiGet<Disclosure[]>("/api/disclosures?limit=100", []);
  return <><PageHeader eyebrow="Resmî açıklamalar" title="KAP Bildirimleri" description="Borsa İstanbul şirketlerinin güncel bildirimleri, sınıflandırmaları ve indirilebilir ekleri."/><ServiceNotice show={!result.ok}/>{result.data.length ? <PaginatedItems pageSize={15} className="panel-flat overflow-hidden" items={result.data.map((item, index) => <Link href={`/kap/${item.disclosure_index}`} key={item.disclosure_index} className={`group grid gap-4 p-4 transition hover:bg-[var(--surface-hover)] sm:grid-cols-[150px_minmax(0,1fr)_110px_20px] sm:items-center sm:p-5 ${index ? "border-t" : ""}`} style={{ borderColor: "var(--border)" }}><div><p className="text-xs font-medium">{formatDate(item.published_at, true)}</p><p className="mt-1 text-[10px] uppercase tracking-wider text-[var(--text-muted)]">#{item.disclosure_index}</p></div><div className="min-w-0"><div className="mb-2"><TickerPills tickers={item.ticker_codes}/></div><h2 className="line-clamp-2 text-sm font-medium leading-5 group-hover:text-[var(--primary)]">{item.subject || item.summary || item.kap_title}</h2><p className="mt-1 text-[11px] text-[var(--text-muted)]">{item.disclosure_class || item.disclosure_category || "Şirket bildirimi"}</p></div><div className="text-xs text-[var(--text-secondary)]">{item.attachment_count ? <span className="flex items-center gap-1.5"><Icon name="file" size={14}/>{item.attachment_count} ek</span> : "Ek yok"}</div><Icon name="chevron" size={16} className="hidden text-[var(--text-muted)] sm:block"/></Link>)}/> : <div className="panel-flat"><EmptyState/></div>}</>;
}
