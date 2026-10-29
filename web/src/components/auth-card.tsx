import { Icon } from "./icon";

/** Giriş, kayıt ve parola sayfalarının ortak ortalanmış kartı. */
export function AuthCard({ eyebrow, title, notice, children, footer }: { eyebrow: string; title: string; notice?: React.ReactNode; children: React.ReactNode; footer?: React.ReactNode }) {
  return <div className="mx-auto flex min-h-[60vh] max-w-sm flex-col justify-center py-10">
    <div className="panel-flat p-6">
      <div className="mb-6 flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded bg-[var(--primary-soft)] text-[var(--primary)]"><Icon name="activity" size={20}/></span>
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--text-muted)]">{eyebrow}</p>
          <h1 className="text-lg font-semibold">{title}</h1>
        </div>
      </div>
      {notice}
      {children}
      {footer && <div className="mt-5 space-y-1.5 border-t pt-4 text-xs text-[var(--text-muted)]" style={{ borderColor: "var(--border)" }}>{footer}</div>}
    </div>
  </div>;
}

export function AuthNotice({ children, tone = "positive" }: { children: React.ReactNode; tone?: "positive" | "negative" }) {
  return <p role={tone === "negative" ? "alert" : "status"} className="mb-4 rounded border px-3 py-2 text-xs leading-5" style={{ color: `var(--${tone})`, borderColor: `var(--${tone})`, background: `var(--${tone}-soft)` }}>{children}</p>;
}
