import Link from "next/link";
import { eventName, relativeTime } from "@/lib/format";
import type { Evaluation } from "@/lib/types";
import { Icon } from "./icon";

/** Haber/KAP kaydının AI değerlendirme sayfası; kaynak kimlikleri haber id'si ve KAP bildirim numarasıdır. */
export function evaluationSourceHref(item: Pick<Evaluation, "source_type" | "source_id">) {
  return item.source_type === "news" ? `/haberler/${item.source_id}` : `/kap/${item.source_id}`;
}

/** Tier 1 hızlı ön elemedir; Tier 2 aynı içeriğin daha güçlü modelle yapılan ayrıntılı incelemesidir. */
export function tierLabel(tier: number) {
  return tier >= 2 ? "Ayrıntılı analiz" : "Ön değerlendirme";
}

export function SourceAnalyses({ items }: { items: Evaluation[] }) {
  if (!items.length) return null;
  // Tier 2 aynı kaynağın daha ayrıntılı ikinci incelemesidir ve geçerli değerlendirme odur;
  // önceki ön değerlendirmeler katlanır ki aynı habere iki farklı etki skoru yan yana görünmesin.
  const [primary, ...earlier] = [...items].sort((a, b) => b.tier - a.tier || b.id - a.id);
  return <section aria-label="AI değerlendirmesi" className="my-6 space-y-2">
    <Link href={`/analizler/${primary.id}`} className="flex items-start gap-3 rounded border p-4 transition hover:bg-[var(--surface-hover)]" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded bg-[var(--primary-soft)] text-[var(--primary)]"><Icon name="spark" size={16}/></span>
      <span className="min-w-0 flex-1"><span className="eyebrow">AI değerlendirmesi · {tierLabel(primary.tier)} · {eventName(primary.event_type)}</span><span className="mt-1 block text-sm font-medium leading-5">{primary.summary || "Değerlendirme detayı"}</span><span className="mt-1 block text-[11px] text-[var(--text-muted)]">Etki {primary.impact_score ?? "—"} · {relativeTime(primary.created_at)}</span></span>
      <Icon name="arrow" className="mt-1 shrink-0 text-[var(--primary)]"/>
    </Link>
    {earlier.length > 0 && <details className="rounded border px-4 py-2.5 text-xs" style={{ borderColor: "var(--border)" }}>
      <summary className="cursor-pointer text-[var(--text-muted)]">{earlier.length === 1 ? `Ön değerlendirme (Etki ${earlier[0].impact_score ?? "—"})` : `${earlier.length} önceki değerlendirme`} — ayrıntılı analizden önce yapılan hızlı inceleme</summary>
      <div className="mt-2 space-y-1.5">{earlier.map((item) => <Link key={item.id} href={`/analizler/${item.id}`} className="flex items-start gap-2 rounded px-2 py-1.5 transition hover:bg-[var(--surface-hover)]">
        <span className="min-w-0 flex-1"><span className="block leading-5 text-[var(--text-secondary)]">{item.summary || "Değerlendirme detayı"}</span><span className="block text-[11px] text-[var(--text-muted)]">{tierLabel(item.tier)} · Etki {item.impact_score ?? "—"} · {relativeTime(item.created_at)}</span></span>
        <Icon name="arrow" size={14} className="mt-1 shrink-0 text-[var(--text-muted)]"/>
      </Link>)}</div>
    </details>}
  </section>;
}
