import Link from "next/link";
import { Icon } from "./icon";

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: React.ReactNode }) {
  return <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div>{eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}<h1 className="page-title">{title}</h1>{description && <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">{description}</p>}</div>{actions}</div>;
}
export function SectionTitle({ title, subtitle, href }: { title: string; subtitle?: string; href?: string }) {
  return <div className="mb-4 flex items-end justify-between gap-3"><div><h2 className="text-base font-semibold tracking-[-0.02em]">{title}</h2>{subtitle && <p className="mt-1 text-xs text-[var(--text-muted)]">{subtitle}</p>}</div>{href && <Link href={href} className="flex items-center gap-1 text-xs font-medium text-[var(--primary)]">Tümünü gör <Icon name="arrow" size={14}/></Link>}</div>;
}
export function EmptyState({ title = "Henüz veri yok", description = "Veri toplayıcıları çalıştığında sonuçlar burada görünecek.", compact = false }: { title?: string; description?: string; compact?: boolean }) {
  return <div className={`grid place-items-center text-center ${compact ? "min-h-32 p-5" : "min-h-56 p-8"}`}><div><span className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-full bg-[var(--surface-raised)] text-[var(--text-muted)]"><Icon name="activity"/></span><p className="text-sm font-medium">{title}</p><p className="mx-auto mt-1 max-w-sm text-xs leading-5 text-[var(--text-muted)]">{description}</p></div></div>;
}
export function ServiceNotice({ show }: { show: boolean }) {
  if (!show) return null;
  return <div className="mb-6 flex items-center gap-3 rounded-[12px] border px-4 py-3 text-xs text-[var(--warning)]" style={{ borderColor: "color-mix(in srgb, var(--warning) 25%, transparent)", background: "var(--warning-soft)" }}><span className="h-2 w-2 rounded-full bg-[var(--warning)]"/> API servisine şu anda ulaşılamıyor. Arayüz hazır; servis açıldığında veriler otomatik görünecek.</div>;
}
export function TickerPills({ tickers }: { tickers: string[] }) {
  if (!tickers.length) return <span className="text-xs text-[var(--text-muted)]">Genel piyasa</span>;
  return <div className="flex flex-wrap gap-1.5">{tickers.map((ticker) => <Link href={`/piyasalar/${ticker}`} key={ticker} className="rounded-md bg-[var(--primary-soft)] px-2 py-1 text-[11px] font-semibold text-[var(--primary)] transition hover:bg-[var(--primary)] hover:text-[var(--primary-contrast)]">{ticker}</Link>)}</div>;
}
export function ScoreRing({ score, label = "Skor", size = 82 }: { score: number | null; label?: string; size?: number }) {
  const safe = Math.max(0, Math.min(100, score ?? 0));
  return <div className="relative grid place-items-center" style={{ width: size, height: size }}><svg className="-rotate-90" width={size} height={size} viewBox="0 0 42 42"><circle cx="21" cy="21" r="17" fill="none" stroke="var(--border)" strokeWidth="3"/><circle cx="21" cy="21" r="17" fill="none" stroke="var(--primary)" strokeWidth="3" strokeLinecap="round" strokeDasharray={`${safe * 1.068} 106.8`}/></svg><div className="absolute text-center"><p className="text-lg font-semibold leading-none">{score ?? "—"}</p><p className="mt-1 text-[8px] uppercase tracking-wider text-[var(--text-muted)]">{label}</p></div></div>;
}
export function Breadcrumbs({ items }: { items: { label: string; href?: string }[] }) {
  return <nav className="mb-5 flex items-center gap-1.5 text-xs text-[var(--text-muted)]">{items.map((item, index) => <span key={`${item.label}-${index}`} className="flex items-center gap-1.5">{index > 0 && <span>/</span>}{item.href ? <Link href={item.href} className="hover:text-[var(--text)]">{item.label}</Link> : <span className="text-[var(--text-secondary)]">{item.label}</span>}</span>)}</nav>;
}
