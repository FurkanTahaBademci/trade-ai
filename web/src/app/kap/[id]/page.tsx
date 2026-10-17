import type { Metadata } from "next";
import { cache } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { apiGet, isApiNotFound } from "@/lib/api";
import type { Disclosure, Evaluation } from "@/lib/types";
import { formatDate, formatNumber } from "@/lib/format";
import { Breadcrumbs, EmptyState, TickerPills } from "@/components/ui";
import { Icon } from "@/components/icon";
import { SourceAnalyses } from "@/components/source-analysis";
import { pageTitle } from "@/lib/page-title";
import { disclosureHeadline, parseKapBody } from "@/lib/kap-body";

const loadDisclosure = cache((id: string) => apiGet<Disclosure | null>(`/api/disclosures/${id}`, null));

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const item = (await loadDisclosure(id)).data;
  return { title: item ? pageTitle(disclosureHeadline(item), "KAP Bildirimi", 80) : "KAP Bildirimi", description: item?.summary ? pageTitle(item.summary, "", 160) : undefined };
}

/** KAP form metni: etiket–değer çiftleri tanım listesi, açıklamalar paragraf olarak. */
function DisclosureBody({ text }: { text: string }) {
  const blocks = parseKapBody(text);
  return <div className="space-y-4 text-sm leading-7 text-[var(--text-secondary)]">{blocks.map((block, index) => {
    if (block.kind === "heading") return <h2 key={index} className="pt-1 text-sm font-semibold text-[var(--text)]">{block.text}</h2>;
    if (block.kind === "paragraph") return <p key={index} className="whitespace-pre-wrap break-words">{block.text}</p>;
    return <dl key={index} className="divide-y rounded border" style={{ borderColor: "var(--border)" }}>{block.items.map((field, i) => <div key={i} className="grid gap-0.5 px-3 py-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] sm:gap-6" style={{ borderColor: "var(--border)" }}><dt className="text-xs leading-5 text-[var(--text-muted)] sm:text-sm sm:leading-6">{field.label}</dt><dd className="break-words font-medium leading-6 text-[var(--text)]">{field.value}</dd></div>)}</dl>;
  })}</div>;
}

export default async function DisclosureDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; const numericId = /^\d+$/.test(id);
  const [result, analyses] = await Promise.all([loadDisclosure(id), numericId ? apiGet<Evaluation[]>(`/api/evaluations?source_type=kap&source_id=${id}&status=succeeded&limit=3`, [], { revalidate: 60 }) : Promise.resolve({ data: [] as Evaluation[], ok: true as const })]); const item = result.data;
  if (isApiNotFound(result)) notFound();
  if (!item) return <div className="panel-flat"><EmptyState title="Bildirim bulunamadı"/></div>;
  return <><Breadcrumbs items={[{ label: "KAP Bildirimleri", href: "/kap" }, { label: `#${item.disclosure_index}` }]}/><div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]"><article><div className="mb-5"><div className="mb-3 flex flex-wrap items-center gap-3"><TickerPills tickers={item.ticker_codes}/><span className="pill">{item.disclosure_class || "Bildirim"}</span>{item.is_late && <span className="pill pill-negative">Geç bildirim</span>}</div><h1 className="text-2xl font-semibold leading-tight tracking-[-0.035em] sm:text-3xl">{item.subject || item.summary || item.kap_title}</h1><p className="mt-3 flex items-center gap-1.5 text-xs text-[var(--text-muted)]"><Icon name="clock" size={13}/>{formatDate(item.published_at, true)} · KAP #{item.disclosure_index}</p></div><SourceAnalyses items={analyses.data}/><div className="panel-flat p-4 sm:p-5">{item.body_text ? <DisclosureBody text={item.body_text}/> : <p className="whitespace-pre-wrap text-sm leading-7 text-[var(--text-secondary)]">{item.summary || "Bildirim metni henüz alınmadı."}</p>}</div></article><aside><div className="panel-flat p-4"><h2 className="text-sm font-semibold">Ek dosyalar</h2><p className="mt-1 text-xs text-[var(--text-muted)]">{item.attachments?.length || 0} dosya</p><div className="mt-4 space-y-2">{item.attachments?.length ? item.attachments.map((file) => <Link key={file.obj_id} href={`/api/attachments/${item.disclosure_index}/${file.obj_id}`} target="_blank" className="flex items-center gap-3 rounded border p-3 transition hover:bg-[var(--surface-hover)]" style={{ borderColor: "var(--border)" }}><span className="grid h-9 w-9 place-items-center rounded bg-[var(--primary-soft)] text-[var(--primary)]"><Icon name="file" size={16}/></span><span className="min-w-0 flex-1"><span className="block truncate text-xs font-medium">{file.file_name}</span><span className="mt-1 block text-[10px] uppercase text-[var(--text-muted)]">{file.file_extension ? `${file.file_extension} dosyası` : "Dosya"}</span></span><Icon name="external" size={14} className="text-[var(--text-muted)]"/></Link>) : <EmptyState compact title="Ek dosya yok"/>}</div></div></aside></div></>;
}
