import Link from "next/link";
import { startGoogleAction } from "@/app/giris/actions";

const buttonClass = "flex h-11 w-full items-center justify-center gap-2.5 rounded border bg-[var(--surface)] px-4 text-sm font-semibold text-[var(--text)] transition hover:bg-[var(--surface-hover)]";

function GoogleLogo() {
  return <svg aria-hidden="true" width="18" height="18" viewBox="0 0 48 48">
    <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/>
    <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>
    <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/>
    <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C36.9 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/>
  </svg>;
}

export function OrDivider({ label }: { label: string }) {
  return <div className="my-5 flex items-center gap-3 text-[11px] text-[var(--text-muted)]">
    <span className="h-px flex-1 bg-[var(--border)]"/>{label}<span className="h-px flex-1 bg-[var(--border)]"/>
  </div>;
}

export function GoogleLoginButton({ next }: { next: string }) {
  return <form action={startGoogleAction}>
    <input type="hidden" name="mode" value="login"/>
    <input type="hidden" name="next" value={next}/>
    <button className={buttonClass} style={{ borderColor: "var(--border-strong)" }}><GoogleLogo/>Google ile giriş yap</button>
  </form>;
}

/** Kayıt: koşul onayı (ve kapalı betada davet kodu) Google'a gitmeden alınır. */
export function GoogleSignupForm({ inviteRequired }: { inviteRequired: boolean }) {
  return <form action={startGoogleAction} className="space-y-3">
    <input type="hidden" name="mode" value="signup"/>
    {inviteRequired && <label className="block">
      <span className="mb-1.5 block text-[11px] font-medium text-[var(--text-muted)]">Davet kodu</span>
      <input className="input" name="invite_code" type="text" autoComplete="off" autoCapitalize="characters" spellCheck={false} required placeholder="XXXX-XXXX-XXXX"/>
    </label>}
    <label className="flex items-start gap-2 text-xs leading-5 text-[var(--text-secondary)]">
      <input type="checkbox" name="accept_terms" required className="mt-1"/>
      <span><Link href="/gizlilik" target="_blank" className="font-medium text-[var(--primary)]">Kullanım koşullarını ve aydınlatma metnini</Link> okudum, kabul ediyorum.</span>
    </label>
    <button className={buttonClass} style={{ borderColor: "var(--border-strong)" }}><GoogleLogo/>Google ile kayıt ol</button>
  </form>;
}

export function GoogleLinkButton() {
  return <form action={startGoogleAction}>
    <input type="hidden" name="mode" value="link"/>
    <button className="pill inline-flex items-center gap-2 hover:text-[var(--text)]"><GoogleLogo/>Google hesabını bağla</button>
  </form>;
}
