import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { apiGet, isApiNotFound } from "@/lib/api";
import type { NewsArticle } from "@/lib/types";
import { formatDate, sourceName } from "@/lib/format";
import { Breadcrumbs, EmptyState, TickerPills } from "@/components/ui";
import { Icon } from "@/components/icon";

export const metadata: Metadata = { title: "Haber Detayı" };

export default async function NewsDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; const result = await apiGet<NewsArticle | null>(`/api/news/${id}`, null); const item = result.data;
  if (isApiNotFound(result)) notFound();
  if (!item) return <div className="panel-flat"><EmptyState title="Haber bulunamadı" description="İçerik kaldırılmış veya servis şu anda erişilemiyor olabilir."/></div>;
  return <><Breadcrumbs items={[{ label: "Haberler", href: "/haberler" }, { label: sourceName(item.source) }]}/><article className="mx-auto max-w-4xl"><div className="mb-5 flex flex-wrap items-center gap-3"><span className="pill pill-primary">{sourceName(item.source)}</span><span className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]"><Icon name="clock" size={13}/>{formatDate(item.published_at, true)}</span>{item.author && <span className="text-xs text-[var(--text-muted)]">• {item.author}</span>}</div><h1 className="text-2xl font-semibold leading-tight tracking-[-0.035em] sm:text-3xl">{item.title}</h1><div className="my-6"><TickerPills tickers={item.ticker_codes}/></div><div className="panel-flat p-4 sm:p-5"><p className="text-sm leading-7 text-[var(--text-secondary)]">{item.summary || "Bu haber için RSS özeti sağlanmadı. İçeriğin tamamını kaynak sayfasında okuyabilirsiniz."}</p><div className="mt-7 border-t pt-5" style={{ borderColor: "var(--border)" }}><Link href={item.canonical_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded bg-[var(--primary)] px-4 py-2.5 text-sm font-semibold text-[var(--primary-contrast)]">Kaynakta oku <Icon name="external" size={15}/></Link></div></div></article></>;
}
