import Link from "next/link";
import { eventName, relativeTime } from "@/lib/format";
import type { Evaluation } from "@/lib/types";
import { Icon } from "./icon";

/** Haber/KAP kaydının AI değerlendirme sayfası; kaynak kimlikleri haber id'si ve KAP bildirim numarasıdır. */
export function evaluationSourceHref(item: Pick<Evaluation, "source_type" | "source_id">) {
  return item.source_type === "news" ? `/haberler/${item.source_id}` : `/kap/${item.source_id}`;
}

export function SourceAnalyses({ items }: { items: Evaluation[] }) {
  if (!items.length) return null;
  // Tier 2 aynı kaynağın daha ayrıntılı ikinci incelemesidir; önce o gösterilir.
  const ordered = [...items].sort((a, b) => b.tier - a.tier || b.id - a.id);
  return <section aria-label="AI değerlendirmesi" className="my-6 space-y-2">{ordered.map((item) => <Link key={item.id} href={`/analizler/${item.id}`} className="flex items-start gap-3 rounded border p-4 transition hover:bg-[var(--surface-hover)]" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
    <span className="grid h-9 w-9 shrink-0 place-items-center rounded bg-[var(--primary-soft)] text-[var(--primary)]"><Icon name="spark" size={16}/></span>
    <span className="min-w-0 flex-1"><span className="eyebrow">AI değerlendirmesi · Tier {item.tier} · {eventName(item.event_type)}</span><span className="mt-1 block text-sm font-medium leading-5">{item.summary || "Değerlendirme detayı"}</span><span className="mt-1 block text-[11px] text-[var(--text-muted)]">Etki {item.impact_score ?? "—"} · {relativeTime(item.created_at)}</span></span>
    <Icon name="arrow" className="mt-1 shrink-0 text-[var(--primary)]"/>
  </Link>)}</section>;
}
