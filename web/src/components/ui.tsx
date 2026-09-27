import Link from "next/link";
import { Icon, type IconName } from "./icon";

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: React.ReactNode }) {
  return <div className="mb-4 border-b border-[var(--border)] pb-4"><div className="min-w-0">{eyebrow && <p className="eyebrow mb-1.5">{eyebrow}</p>}<h1 className="page-title">{title}</h1>{description && <p className="mt-1.5 max-w-3xl text-xs leading-5 text-[var(--text-secondary)]">{description}</p>}</div>{actions && <div className="mt-3 flex flex-wrap items-center gap-2">{actions}</div>}</div>;
}
export function SectionTitle({ title, subtitle, href }: { title: string; subtitle?: string; href?: string }) {
  return <div className="mb-4 flex items-end justify-between gap-3"><div><h2 className="text-base font-semibold tracking-[-0.02em]">{title}</h2>{subtitle && <p className="mt-1 text-xs text-[var(--text-muted)]">{subtitle}</p>}</div>{href && <Link href={href} className="flex items-center gap-1 text-xs font-medium text-[var(--primary)]">Tümünü gör <Icon name="arrow" size={14}/></Link>}</div>;
}
export function EmptyState({ title = "Henüz veri yok", description = "Veri toplayıcıları çalıştığında sonuçlar burada görünecek.", compact = false }: { title?: string; description?: string; compact?: boolean }) {
  return <div className={`grid place-items-center text-center ${compact ? "min-h-32 p-5" : "min-h-56 p-8"}`}><div><span className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-full bg-[var(--surface-raised)] text-[var(--text-muted)]"><Icon name="activity"/></span><p className="text-sm font-medium">{title}</p><p className="mx-auto mt-1 max-w-sm text-xs leading-5 text-[var(--text-muted)]">{description}</p></div></div>;
}
export function ServiceNotice({ show }: { show: boolean }) {
  if (!show) return null;
  return <div className="mb-6 flex items-center gap-3 rounded border px-4 py-3 text-xs text-[var(--warning)]" style={{ borderColor: "color-mix(in srgb, var(--warning) 25%, transparent)", background: "var(--warning-soft)" }}><span className="h-2 w-2 rounded-full bg-[var(--warning)]"/> API servisine şu anda ulaşılamıyor. Bazı veriler eksik olabilir. Yenileyerek tekrar deneyebilirsiniz.</div>;
}
export function TickerPills({ tickers }: { tickers: string[] }) {
  if (!tickers.length) return <span className="text-xs text-[var(--text-muted)]">Genel piyasa</span>;
  return <div className="flex flex-wrap gap-1.5">{tickers.map((ticker) => <Link href={`/piyasalar/${ticker}`} key={ticker} className="rounded-md bg-[var(--primary-soft)] px-2 py-1 text-[11px] font-semibold text-[var(--primary)] transition hover:bg-[var(--primary)] hover:text-[var(--primary-contrast)]">{ticker}</Link>)}</div>;
}
export function ScoreMeter({ score, label = "Skor", size = 82 }: { score: number | null; label?: string; size?: number }) {
  const safe = Math.max(0, Math.min(100, score ?? 0));
  return <div className="shrink-0" style={{ width: Math.max(64, size) }} aria-label={`${label}: ${score ?? "veri yok"}`}><div className="mb-1 flex items-baseline justify-between gap-2"><span className="text-[10px] uppercase text-[var(--text-muted)]">{label}</span><span className="terminal-mono text-lg font-semibold text-[var(--primary)]">{score == null ? "—" : Math.round(score)}</span></div><div className="h-1 bg-[var(--border)]" aria-hidden="true"><div className="h-full bg-[var(--primary)]" style={{ width: `${safe}%` }}/></div></div>;
}
export function DataMetric({ label, value, meta, suffix, tone, icon }: { label: string; value: string; meta?: string; suffix?: string; tone?: boolean | "positive" | "negative" | "warning"; icon?: IconName }) {
  const color = tone === true || tone === "positive" ? "var(--positive)" : tone === false || tone === "negative" ? "var(--negative)" : tone === "warning" ? "var(--warning)" : "var(--text)";
  return <div className="panel-flat min-w-0 px-4 py-3"><div className="flex items-center justify-between gap-2"><p className="eyebrow tracking-wider">{label}</p>{icon && <Icon name={icon} size={14} className="shrink-0 text-[var(--text-muted)]"/>}</div><p className="terminal-mono mt-2 break-words text-xl font-semibold leading-7" style={{ color }}>{value}{suffix && <span className="ml-1 text-xs font-normal text-[var(--text-muted)]">{suffix}</span>}</p>{meta && <p className="mt-1 text-[11px] leading-4 text-[var(--text-muted)]">{meta}</p>}</div>;
}
export function Breadcrumbs({ items }: { items: { label: string; href?: string }[] }) {
  return <nav aria-label="Sayfa yolu" className="mb-4 flex-wrap flex items-center gap-1.5 text-xs text-[var(--text-muted)]">{items.map((item, index) => <span key={`${item.label}-${index}`} className="flex items-center gap-1.5">{index > 0 && <span>/</span>}{item.href ? <Link href={item.href} className="hover:text-[var(--text)]">{item.label}</Link> : <span className="text-[var(--text-secondary)]">{item.label}</span>}</span>)}</nav>;
}
