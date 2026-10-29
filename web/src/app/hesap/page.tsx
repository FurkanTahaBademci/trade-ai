import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { PageHeader, SectionTitle } from "@/components/ui";
import { GoogleLinkButton } from "@/components/google-sign-in";
import { LogoutForm } from "@/components/logout-form";
import { describeUserAgent } from "@/lib/account";
import { accountRequest, currentAccount, serviceRequest, sessionToken } from "@/lib/account-server";
import { formatDate } from "@/lib/format";
import { changePasswordAction, deleteAccountAction, revokeOtherSessionsAction, revokeSessionAction, unlinkGoogleAction, updateProfileAction } from "./actions";

export const metadata: Metadata = { title: "Hesabım", robots: { index: false, follow: false } };

type Identity = { provider: string; email: string; created_at: string | null; last_used_at: string | null };
type AccountSession = { id: number; created_at: string; last_seen_at: string; expires_at: string; user_agent: string | null; ip_address: string | null; current: boolean };

const label = "mb-1.5 block text-[11px] font-medium text-[var(--text-muted)]";
const primaryButton = "h-10 rounded bg-[var(--primary)] px-4 text-xs font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)]";

export default async function AccountPage({ searchParams }: { searchParams: Promise<{ result?: string; message?: string }> }) {
  const [token, account, notice] = await Promise.all([sessionToken(), currentAccount(), searchParams]);
  if (!token || !account) redirect("/giris?next=/hesap");
  const [sessions, identities, config] = await Promise.all([
    accountRequest<AccountSession[]>("/api/me/sessions", token),
    accountRequest<Identity[]>("/api/me/identities", token),
    serviceRequest<{ google_enabled?: boolean }>("/api/auth/config"),
  ]);
  const others = sessions.ok ? sessions.data.filter((item) => !item.current).length : 0;
  const google = identities.ok ? identities.data.find((item) => item.provider === "google") : undefined;
  const googleEnabled = config.ok && config.data.google_enabled === true;
  // Yalnız Google ile açılmış hesap: mevcut parola istenmez, silme onayı e-postayla.
  const hasPassword = account.has_password !== false;

  return <>
    <PageHeader eyebrow="Hesap" title="Hesabım" description="Profilin, parolan, bildirimlerin, açık oturumların ve hesabının silinmesi." actions={<LogoutForm className="pill hover:text-[var(--text)]"/>}/>
    {notice.message && <div role="status" className={`mb-5 rounded border px-4 py-3 text-sm ${notice.result === "ok" ? "text-[var(--positive)]" : "text-[var(--negative)]"}`} style={{ borderColor: notice.result === "ok" ? "var(--positive)" : "var(--negative)", background: notice.result === "ok" ? "var(--positive-soft)" : "var(--negative-soft)" }}>{notice.message}</div>}

    <div className="grid gap-4 xl:grid-cols-2">
      <section className="panel-flat p-5">
        <SectionTitle title="Profil" subtitle={`Üyelik ${account.created_at ? formatDate(account.created_at) : "—"}${account.role === "admin" ? " · Yönetici" : ""}`}/>
        <form action={updateProfileAction} className="space-y-4">
          <label className="block"><span className={label}>E-posta</span><input className="input opacity-70" value={account.email} readOnly aria-readonly/></label>
          <label className="block"><span className={label}>Görünen ad</span><input className="input" name="display_name" defaultValue={account.display_name} maxLength={64} required autoComplete="nickname"/></label>
          <button className={primaryButton}>Kaydet</button>
        </form>
        <p className="mt-4 text-[11px] leading-5 text-[var(--text-muted)]">İzleme listen hesabında saklanır; <Link href="/izleme-listesi" className="text-[var(--primary)]">izleme listesi</Link> her cihazda aynı görünür.</p>
      </section>

      <section className="panel-flat p-5">
        <SectionTitle title={hasPassword ? "Parola" : "Parola belirle"} subtitle={hasPassword ? "Değiştirince diğer cihazlardaki oturumlar kapanır" : "Şu an yalnız Google ile giriş yapıyorsun"}/>
        <form action={changePasswordAction} className="space-y-4">
          {/* Parola yöneticileri hangi hesabın parolası olduğunu anlasın. */}
          <input type="text" name="username" value={account.email} autoComplete="username" readOnly hidden/>
          {hasPassword && <label className="block"><span className={label}>Mevcut parola</span><input className="input" type="password" name="current_password" autoComplete="current-password" required/></label>}
          <label className="block"><span className={label}>Yeni parola</span><input className="input" type="password" name="new_password" autoComplete="new-password" minLength={10} required/></label>
          <label className="block"><span className={label}>Yeni parola (tekrar)</span><input className="input" type="password" name="new_password_confirm" autoComplete="new-password" minLength={10} required/></label>
          <button className={primaryButton}>{hasPassword ? "Parolayı değiştir" : "Parolayı kaydet"}</button>
        </form>
      </section>
    </div>

    <div className="mt-4 grid gap-4 xl:grid-cols-2">
      <section className="panel-flat p-5">
        <SectionTitle title="Bildirimler" subtitle="Telegram ve günlük özet"/>
        <p className="mb-4 text-xs leading-5 text-[var(--text-secondary)]">İzleme listendeki ve paper portföylerindeki hisselerin skor etiketi değişince Telegram bildirimi, işlem günü sonunda portföy özeti al.</p>
        <Link href="/hesap/bildirimler" className="pill hover:text-[var(--text)]">Bildirim ayarları</Link>
      </section>
      {(google || googleEnabled) && <section className="panel-flat p-5">
        <SectionTitle title="Google ile giriş" subtitle={google ? "Bağlı" : "Bağlı değil"}/>
        {google ? <>
          <p className="mb-4 text-xs leading-5 text-[var(--text-secondary)]"><span className="font-medium text-[var(--text)]">{google.email || "Google hesabı"}</span> ile giriş yapabilirsin.{google.last_used_at ? ` Son kullanım: ${formatDate(google.last_used_at, true)}.` : ""}</p>
          {hasPassword
            ? <form action={unlinkGoogleAction}><button className="pill hover:text-[var(--negative)]">Google bağlantısını kaldır</button></form>
            : <p className="text-[11px] leading-5 text-[var(--text-muted)]">Bağlantıyı kaldırmak için önce bir parola belirle.</p>}
        </> : <>
          <p className="mb-4 text-xs leading-5 text-[var(--text-secondary)]">Google hesabını bağlarsan parolasız, tek tıkla giriş yapabilirsin.</p>
          <GoogleLinkButton/>
        </>}
      </section>}
    </div>

    <section className="mt-6">
      <SectionTitle title="Açık oturumlar" subtitle={sessions.ok ? `${sessions.data.length} oturum · 30 gün sonra kendiliğinden kapanır` : sessions.message}/>
      {sessions.ok && <div className="table-shell overflow-x-auto"><table className="data-table min-w-[640px]"><thead><tr><th>Cihaz</th><th>IP</th><th>Açılış</th><th>Son görülme</th><th/></tr></thead><tbody>{sessions.data.map((item) => <tr key={item.id}>
        <td><span className="font-medium">{describeUserAgent(item.user_agent)}</span>{item.current && <span className="pill pill-positive ml-2">Bu cihaz</span>}</td>
        <td className="terminal-mono text-[var(--text-muted)]">{item.ip_address ?? "—"}</td>
        <td>{formatDate(item.created_at, true)}</td>
        <td>{formatDate(item.last_seen_at, true)}</td>
        <td className="text-right">{!item.current && <form action={revokeSessionAction}><input type="hidden" name="session_id" value={item.id}/><button className="pill hover:text-[var(--negative)]">Kapat</button></form>}</td>
      </tr>)}</tbody></table></div>}
      {others > 0 && <form action={revokeOtherSessionsAction} className="mt-3"><button className="pill hover:text-[var(--negative)]">Diğer {others} oturumu kapat</button></form>}
    </section>

    <section className="mt-8">
      <SectionTitle title="Hesabı sil" subtitle="Geri alınamaz"/>
      <form action={deleteAccountAction} className="panel-flat max-w-xl space-y-4 p-5" style={{ borderColor: "var(--negative)" }}>
        <p className="text-xs leading-5 text-[var(--text-secondary)]">Hesabın, izleme listen ve tüm oturumların kalıcı olarak silinir. Aynı e-postayla daha sonra yeniden kayıt olabilirsin.</p>
        <input type="text" name="username" value={account.email} autoComplete="username" readOnly hidden/>
        {hasPassword
          ? <label className="block"><span className={label}>Parola</span><input className="input" type="password" name="password" autoComplete="current-password" required/></label>
          : <label className="block"><span className={label}>Onay için e-posta adresini yaz</span><input className="input" type="email" name="email" autoComplete="off" placeholder={account.email} required/></label>}
        <label className="flex items-center gap-2 text-xs"><input type="checkbox" name="confirm" required/>Hesabımın ve verilerimin silineceğini anlıyorum.</label>
        <button className="h-10 rounded border px-4 text-xs font-semibold text-[var(--negative)] transition hover:bg-[var(--negative-soft)]" style={{ borderColor: "var(--negative)" }}>Hesabımı kalıcı olarak sil</button>
      </form>
    </section>
  </>;
}
