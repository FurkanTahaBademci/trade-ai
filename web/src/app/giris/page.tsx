import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { LoginForm } from "@/components/login-form";
import { Icon } from "@/components/icon";
import { ADMIN_SESSION_COOKIE, adminAuthState, safeNextPath } from "@/lib/admin-auth";

export const metadata: Metadata = { title: "Yönetici Girişi", robots: { index: false, follow: false } };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string; cikis?: string }> }) {
  const params = await searchParams;
  const next = safeNextPath(params.next);
  const state = adminAuthState((await cookies()).get(ADMIN_SESSION_COOKIE)?.value);
  if (state === "disabled" || state === "authorized") redirect(next);

  return <div className="mx-auto flex min-h-[60vh] max-w-sm flex-col justify-center py-10">
    <div className="panel-flat p-6">
      <div className="mb-6 flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded bg-[var(--primary-soft)] text-[var(--primary)]"><Icon name="activity" size={20}/></span>
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--text-muted)]">Operasyon</p>
          <h1 className="text-lg font-semibold">Yönetici girişi</h1>
        </div>
      </div>
      {params.cikis && <p role="status" className="mb-4 rounded border px-3 py-2 text-xs text-[var(--positive)]" style={{ borderColor: "var(--positive)", background: "var(--positive-soft)" }}>Oturum kapatıldı.</p>}
      {state === "misconfigured"
        ? <div role="alert" className="space-y-2 text-sm leading-6 text-[var(--text-secondary)]">
            <p className="font-semibold text-[var(--negative)]">Yönetici girişi yapılandırılmamış.</p>
            <p>Sunucuda <code>WEB_ADMIN_PASSWORD</code> ortam değişkenini ayarlayıp web servisini yeniden başlatın. Ayrıntılar <code>docs/ADMIN.md</code> dosyasında.</p>
          </div>
        : <LoginForm next={next}/>}
      <p className="mt-5 text-[11px] leading-5 text-[var(--text-muted)]">Sistem ayarları ve backtest ekranları yalnızca yöneticiye açıktır. Diğer tüm ekranlar giriş gerektirmez.</p>
    </div>
  </div>;
}
