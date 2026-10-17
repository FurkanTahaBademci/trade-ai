import Link from "next/link";
import { formatDate, formatNumber, signalName } from "@/lib/format";
import type { SignalMover, SignalMovers } from "@/lib/types";
import { EmptyState, SectionTitle } from "./ui";

export const MOVER_PERIODS = [
  { days: 1, label: "1G", text: "Son gün" },
  { days: 7, label: "1H", text: "Son hafta" },
  { days: 30, label: "1A", text: "Son ay" },
] as const;

export function moverPeriod(value: string | undefined) {
  return MOVER_PERIODS.find((item) => String(item.days) === value) ?? MOVER_PERIODS[1];
}

export function SignalMoversPanel({ movers, days, hrefFor }: { movers: SignalMovers | null; days: number; hrefFor: (days: number) => string }) {
  const period = moverPeriod(String(days));
  const range = movers?.base_date && movers.as_of_date ? `${formatDate(movers.base_date)} → ${formatDate(movers.as_of_date)}` : "Karşılaştırılacak geçmiş skor bekleniyor";
  return <section className="mb-8">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <SectionTitle title="Skor hareketleri" subtitle={`${period.text} içinde bileşik skoru en çok değişen hisseler · ${range}`}/>
      <nav aria-label="Dönem" className="mb-3 flex gap-1.5">{MOVER_PERIODS.map((item) => <Link prefetch={false} key={item.days} href={hrefFor(item.days)} scroll={false} aria-current={item.days === period.days ? "page" : undefined} className={`pill transition ${item.days === period.days ? "pill-primary" : "hover:text-[var(--text)]"}`}>{item.label}</Link>)}</nav>
    </div>
    {movers && (movers.risers.length || movers.fallers.length) ? <div className="grid gap-4 lg:grid-cols-2">
      <MoverList title="Yükselenler" items={movers.risers} positive/>
      <MoverList title="Düşenler" items={movers.fallers} positive={false}/>
    </div> : <div className="panel-flat"><EmptyState compact title="Skor değişimi yok" description="Seçilen dönemin başında skoru olan hisseler biriktikçe en büyük değişimler burada listelenir."/></div>}
  </section>;
}

function MoverList({ title, items, positive }: { title: string; items: SignalMover[]; positive: boolean }) {
  const tone = positive ? "text-[var(--positive)]" : "text-[var(--negative)]";
  return <div className="panel-flat overflow-hidden">
    <p className="eyebrow border-b px-4 py-2.5" style={{ borderColor: "var(--border)" }}>{title}</p>
    {items.length ? <ul>{items.map((item, index) => <li key={item.ticker} className={index ? "border-t" : ""} style={{ borderColor: "var(--border)" }}>
      <Link prefetch={false} href={`/piyasalar/${item.ticker}`} className="flex items-center gap-3 px-4 py-2.5 transition hover:bg-[var(--surface-hover)]">
        <span className="w-16 font-semibold text-[var(--primary)]">{item.ticker}</span>
        <span className="terminal-mono text-xs text-[var(--text-muted)]">{formatNumber(item.previous_score, 0)} → <span className="text-[var(--text)]">{formatNumber(item.composite_score, 0)}</span></span>
        {item.previous_label !== item.signal_label && <span className="hidden text-[10px] text-[var(--text-muted)] sm:inline">{signalName(item.previous_label)} → {signalName(item.signal_label)}</span>}
        <span className={`terminal-mono ml-auto text-sm font-semibold ${tone}`}>{item.change > 0 ? "+" : ""}{formatNumber(item.change, 1)}</span>
      </Link>
    </li>)}</ul> : <p className="px-4 py-3 text-xs text-[var(--text-muted)]">Bu yönde değişim yok.</p>}
  </div>;
}
