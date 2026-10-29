import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { TelegramLinkPanel } from "@/components/telegram-link-panel";
import { PageHeader, SectionTitle } from "@/components/ui";
import { accountRequest, currentAccount, sessionToken } from "@/lib/account-server";
import { formatDate } from "@/lib/format";
import type { AlertPrefs } from "@/lib/types";
import { savePreferencesAction, sendTestMessageAction, unlinkTelegramAction } from "./actions";

export const metadata: Metadata = { title: "Bildirimler", robots: { index: false, follow: false } };

const primaryButton = "h-10 rounded bg-[var(--primary)] px-4 text-xs font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)]";

function Option({ name, checked, disabled, title, children }: { name: string; checked: boolean; disabled?: boolean; title: string; children: React.ReactNode }) {
  return <label className={`flex items-start gap-3 rounded border p-3 ${disabled ? "opacity-60" : "cursor-pointer hover:bg-[var(--surface-hover)]"}`} style={{ borderColor: "var(--border)" }}>
    <input type="checkbox" name={name} defaultChecked={checked} disabled={disabled} className="mt-0.5"/>
    <span><span className="block text-sm font-medium">{title}</span><span className="mt-0.5 block text-xs leading-5 text-[var(--text-muted)]">{children}</span></span>
  </label>;
}

export default async function AlertsPage({ searchParams }: { searchParams: Promise<{ result?: string; message?: string }> }) {
  const [token, account, notice] = await Promise.all([sessionToken(), currentAccount(), searchParams]);
  if (!token || !account) redirect("/giris?next=/hesap/bildirimler");
  const prefs = await accountRequest<AlertPrefs>("/api/me/alerts", token);

  return <>
    <PageHeader eyebrow="Hesap" title="Bildirimler" description="İzleme listen ve paper portföylerin için Telegram bildirimleri ve işlem günü sonu özeti." actions={<Link href="/hesap" className="pill hover:text-[var(--text)]">Hesabım</Link>}/>
    {notice.message && <div role="status" className={`mb-5 rounded border px-4 py-3 text-sm ${notice.result === "ok" ? "text-[var(--positive)]" : "text-[var(--negative)]"}`} style={{ borderColor: notice.result === "ok" ? "var(--positive)" : "var(--negative)", background: notice.result === "ok" ? "var(--positive-soft)" : "var(--negative-soft)" }}>{notice.message}</div>}
    {!prefs.ok ? <p role="alert" className="panel-flat p-5 text-sm text-[var(--negative)]">{prefs.message}</p> : <>
      {!prefs.data.available && <p className="mb-5 rounded border px-4 py-3 text-sm text-[var(--text-secondary)]" style={{ borderColor: "var(--warning)", background: "var(--warning-soft)" }}>Kişisel bildirimler şu an yönetici tarafından kapatıldı. Tercihlerin saklanır; açıldığında kaldığı yerden devam eder.</p>}
      <div className="grid gap-4 xl:grid-cols-2">
        <section className="panel-flat p-5">
          <SectionTitle title="Telegram" subtitle={prefs.data.telegram_linked ? "Bağlı" : "Bağlı değil"}/>
          {prefs.data.telegram_linked ? <div className="space-y-4">
            <p className="text-xs leading-5 text-[var(--text-secondary)]">Bildirimler <span className="font-medium text-[var(--text)]">{prefs.data.telegram_username ? `@${prefs.data.telegram_username}` : "Telegram hesabına"}</span> gidiyor{prefs.data.telegram_linked_at ? ` (bağlanma: ${formatDate(prefs.data.telegram_linked_at, true)})` : ""}.</p>
            <div className="flex flex-wrap gap-2">
              <form action={sendTestMessageAction}><button className="pill hover:text-[var(--text)]">Test mesajı gönder</button></form>
              <form action={unlinkTelegramAction}><button className="pill hover:text-[var(--negative)]">Bağlantıyı kaldır</button></form>
            </div>
          </div> : prefs.data.telegram_available ? <TelegramLinkPanel/> : <p className="text-xs leading-5 text-[var(--text-muted)]">Telegram bildirimleri henüz yapılandırılmadı. E-posta özetini aşağıdan açabilirsin.</p>}
        </section>

        <section className="panel-flat p-5">
          <SectionTitle title="Tercihler" subtitle={prefs.data.last_digest_on ? `Son özet: ${formatDate(prefs.data.last_digest_on)}` : "Henüz özet gönderilmedi"}/>
          <form action={savePreferencesAction} className="space-y-3">
            <Option name="telegram_instant" checked={prefs.data.telegram_instant} title="Anlık etiket değişimi (Telegram)">İzleme listendeki ya da portföylerinde tuttuğun bir hissenin skor etiketi değişince tek mesaj. Skorlar gün içinde 10 dakikada bir güncellenir.</Option>
            <Option name="telegram_digest" checked={prefs.data.telegram_digest} title="Günlük özet (Telegram)">İşlem günü sonunda (~19:20) portföy değerin, günün işlemleri, zarar-kes ve reddedilen emirler, izlediğin hisselerdeki etiket değişimleri.</Option>
            <Option name="email_digest" checked={prefs.data.email_digest} disabled={!prefs.data.email_available} title={`Günlük özet (e-posta · ${account.email})`}>{prefs.data.email_available ? "Aynı özet e-postayla. Portföyün ya da etiket değişimi yoksa gönderilmez." : "E-posta gönderimi henüz yapılandırılmadı."}</Option>
            {!prefs.data.telegram_linked && <p className="text-[11px] leading-5 text-[var(--text-muted)]">Telegram seçenekleri, Telegram bağlandığında çalışır.</p>}
            <button className={primaryButton}>Kaydet</button>
          </form>
        </section>
      </div>
      <p className="mt-6 text-[11px] leading-5 text-[var(--text-muted)]">Bildirimler bilgi amaçlıdır; yatırım tavsiyesi değildir. Paper portföyler sanal bakiyeyle çalışır.</p>
    </>}
  </>;
}
