import type { Metadata } from "next";
import Link from "next/link";
import { apiGet, publicApiUrl } from "@/lib/api";
import type { Disclosure } from "@/lib/types";
import { formatDate, formatNumber } from "@/lib/format";
import { Breadcrumbs, EmptyState, TickerPills } from "@/components/ui";
import { Icon } from "@/components/icon";

export const metadata: Metadata = { title: "KAP Detayı" };

export default async function DisclosureDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; const result = await apiGet<Disclosure | null>(`/api/disclosures/${id}`, null); const item = result.data;
  if (!item) return <div className="panel-flat"><EmptyState title="Bildirim bulunamadı"/></div>;
  return <><Breadcrumbs items={[{ label: "KAP Bildirimleri", href: "/kap" }, { label: `#${item.disclosure_index}` }]}/><div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]"><article><div className="mb-5"><div className="mb-3 flex flex-wrap items-center gap-3"><TickerPills tickers={item.ticker_codes}/><span className="pill">{item.disclosure_class || "Bildirim"}</span>{item.is_late && <span className="pill pill-negative">Geç bildirim</span>}</div><h1 className="text-2xl font-semibold leading-tight tracking-[-0.035em] sm:text-3xl">{item.subject || item.summary || item.kap_title}</h1><p className="mt-3 flex items-center gap-1.5 text-xs text-[var(--text-muted)]"><Icon name="clock" size={13}/>{formatDate(item.published_at, true)} · KAP #{item.disclosure_index}</p></div><div className="panel-flat p-5 sm:p-7"><p className="whitespace-pre-wrap text-sm leading-7 text-[var(--text-secondary)]">{item.body_text || item.summary || "Bildirim metni henüz alınmadı."}</p></div></article><aside><div className="panel-flat p-5"><h2 className="text-sm font-semibold">Ek dosyalar</h2><p className="mt-1 text-xs text-[var(--text-muted)]">{item.attachments?.length || 0} dosya</p><div className="mt-4 space-y-2">{item.attachments?.length ? item.attachments.map((file) => <Link key={file.obj_id} href={publicApiUrl(`/api/disclosures/${item.disclosure_index}/attachments/${file.obj_id}`)} target="_blank" className="flex items-center gap-3 rounded-[10px] border p-3 transition hover:bg-[var(--surface-hover)]" style={{ borderColor: "var(--border)" }}><span className="grid h-9 w-9 place-items-center rounded-lg bg-[var(--primary-soft)] text-[var(--primary)]"><Icon name="file" size={16}/></span><span className="min-w-0 flex-1"><span className="block truncate text-xs font-medium">{file.file_name}</span><span className="mt-1 block text-[10px] uppercase text-[var(--text-muted)]">{file.file_extension || "Dosya"} · {file.size_bytes ? `${formatNumber(file.size_bytes / 1024, 0)} KB` : "—"}</span></span><Icon name="external" size={14} className="text-[var(--text-muted)]"/></Link>) : <EmptyState compact title="Ek dosya yok"/>}</div></div></aside></div></>;
}
