import { createInviteAction, revokeInviteAction, updateUserAction } from "@/app/sistem/actions";
import type { AccountApiResult } from "@/lib/account";
import { formatDate } from "@/lib/format";
import { DataMetric as Metric, EmptyState } from "./ui";

export type AdminUser = { id: number; email: string; display_name: string; role: "user" | "admin"; status: "ACTIVE" | "DISABLED"; email_verified_at: string | null; created_at: string | null; last_login_at: string | null };
export type AdminUsers = { total: number; verified: number; signups_24h: number; paper_portfolios: number; smtp_configured: boolean; registration_mode: "invite" | "open" | "closed"; users: AdminUser[] };
export type Invite = { id: number; code: string; note: string; max_uses: number; used_count: number; expires_at: string | null; revoked_at: string | null; created_at: string | null; state: "active" | "used" | "expired" | "revoked" };

const MODE_TEXT = { invite: "Davet koduyla", open: "Herkese açık", closed: "Kapalı" };
const INVITE_STATE = { active: ["Geçerli", "pill-positive"], used: ["Kullanıldı", ""], expired: ["Süresi doldu", ""], revoked: ["İptal edildi", "pill-negative"] } as const;

function dateText(value: string | null, withTime = false) {
  return value ? formatDate(value, withTime) : "—";
}

function UserAction({ id, change, children, danger }: { id: number; change: string; children: React.ReactNode; danger?: boolean }) {
  return <form action={updateUserAction}><input type="hidden" name="user_id" value={id}/><input type="hidden" name="change" value={change}/><button className={`pill ${danger ? "hover:text-[var(--negative)]" : "hover:text-[var(--text)]"}`}>{children}</button></form>;
}

/** /sistem: kullanıcı hesapları, kayıt modu, SMTP durumu ve davet kodları. */
export function AdminAccountsPanel({ users, invites }: { users: AccountApiResult<AdminUsers>; invites: AccountApiResult<Invite[]> }) {
  if (!users.ok) return <div className="panel-flat"><EmptyState title="Kullanıcı bilgisi alınamadı" description={users.message}/></div>;
  const data = users.data;
  return <>
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4"><Metric label="Toplam kullanıcı" value={data.total.toLocaleString("tr-TR")}/><Metric label="E-postası doğrulanmış" value={data.verified.toLocaleString("tr-TR")} tone="positive"/><Metric label="Son 24 saatte kayıt" value={data.signups_24h.toLocaleString("tr-TR")}/><Metric label="Kullanıcı portföyü" value={(data.paper_portfolios ?? 0).toLocaleString("tr-TR")} meta="Model portföy hariç"/></div>
    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-[var(--text-muted)]">
      <span className="pill">Kayıt: {MODE_TEXT[data.registration_mode]}</span>
      <span className={`pill ${data.smtp_configured ? "pill-positive" : "pill-negative"}`}>SMTP {data.smtp_configured ? "yapılandırılmış" : "yapılandırılmamış"}</span>
      <span>{data.smtp_configured ? "Kayıt modu aşağıdaki Ayarlar bölümünden değişir." : "Doğrulama ve parola sıfırlama e-postaları gönderilmiyor. SMTP_* değişkenlerini ayarla ya da kullanıcıyı buradan elle doğrula."}</span>
    </div>

    <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(300px,.55fr)_minmax(0,1.45fr)]">
      <form action={createInviteAction} className="panel-flat space-y-3 p-4">
        <h3 className="text-sm font-semibold">Davet kodu oluştur</h3>
        <label className="block"><span className="mb-1 block text-[11px] text-[var(--text-muted)]">Not (kime verildi)</span><input className="input" name="note" maxLength={128} placeholder="ör. beta kullanıcısı" autoComplete="off"/></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className="mb-1 block text-[11px] text-[var(--text-muted)]">Kullanım hakkı</span><input className="input" type="number" name="max_uses" min={1} max={1000} defaultValue={1} required/></label>
          <label className="block"><span className="mb-1 block text-[11px] text-[var(--text-muted)]">Geçerlilik</span><select className="input" name="expires_in_days" defaultValue="30"><option value="7">7 gün</option><option value="30">30 gün</option><option value="90">90 gün</option><option value="0">Süresiz</option></select></label>
        </div>
        <button className="h-10 w-full rounded bg-[var(--primary)] px-4 text-xs font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)]">Kod oluştur</button>
      </form>
      <div className="min-w-0">{!invites.ok ? <div className="panel-flat"><EmptyState compact title="Davet kodları alınamadı" description={invites.message}/></div> : invites.data.length ? <div className="table-shell overflow-x-auto"><table className="data-table min-w-[620px]"><thead><tr><th>Kod</th><th>Not</th><th>Kullanım</th><th>Son tarih</th><th>Durum</th><th/></tr></thead><tbody>{invites.data.map((item) => <tr key={item.id}>
        <td className="terminal-mono select-all font-semibold">{item.code}</td>
        <td className="max-w-[180px] truncate" title={item.note}>{item.note || "—"}</td>
        <td>{item.used_count}/{item.max_uses}</td>
        <td>{item.expires_at ? dateText(item.expires_at) : "Süresiz"}</td>
        <td><span className={`pill ${INVITE_STATE[item.state][1]}`}>{INVITE_STATE[item.state][0]}</span></td>
        <td className="text-right">{item.state === "active" && <form action={revokeInviteAction}><input type="hidden" name="invite_id" value={item.id}/><button className="pill hover:text-[var(--negative)]">İptal et</button></form>}</td>
      </tr>)}</tbody></table></div> : <div className="panel-flat"><EmptyState compact title="Henüz davet kodu yok" description="Kapalı betada kayıt için davet kodu gerekir."/></div>}</div>
    </div>

    <div className="mt-4">{data.users.length ? <div className="table-shell overflow-x-auto"><table className="data-table min-w-[900px]"><thead><tr><th>E-posta</th><th>Ad</th><th>Rol</th><th>Durum</th><th>Doğrulama</th><th>Kayıt</th><th>Son giriş</th><th/></tr></thead><tbody>{data.users.map((user) => <tr key={user.id}>
      <td className="font-medium">{user.email}</td>
      <td>{user.display_name || "—"}</td>
      <td>{user.role === "admin" ? <span className="pill pill-positive">Yönetici</span> : "Kullanıcı"}</td>
      <td>{user.status === "ACTIVE" ? "Aktif" : <span className="pill pill-negative">Devre dışı</span>}</td>
      <td>{user.email_verified_at ? dateText(user.email_verified_at) : <span className="text-[var(--warning)]">Bekliyor</span>}</td>
      <td>{dateText(user.created_at)}</td>
      <td>{dateText(user.last_login_at, true)}</td>
      <td><div className="flex justify-end gap-1.5">
        {!user.email_verified_at && <UserAction id={user.id} change="verify">Doğrula</UserAction>}
        {user.role === "admin" ? <UserAction id={user.id} change="make_user">Yöneticiliği al</UserAction> : <UserAction id={user.id} change="make_admin">Yönetici yap</UserAction>}
        {user.status === "ACTIVE" ? <UserAction id={user.id} change="disable" danger>Devre dışı bırak</UserAction> : <UserAction id={user.id} change="enable">Etkinleştir</UserAction>}
      </div></td>
    </tr>)}</tbody></table></div> : <div className="panel-flat"><EmptyState compact title="Henüz kayıtlı kullanıcı yok"/></div>}</div>
  </>;
}
