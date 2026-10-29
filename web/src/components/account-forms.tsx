"use client";

import Link from "next/link";
import { useActionState, useId } from "react";
import {
  type FormState,
  loginAction,
  registerAction,
  requestPasswordResetAction,
  resendVerificationAction,
  resetPasswordAction,
  verifyEmailAction,
} from "@/app/giris/actions";

const INITIAL: FormState = {};

function Field({ label, hint, ...input }: React.InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  const id = useId();
  return <label className="block" htmlFor={id}>
    <span className="mb-1.5 block text-[11px] font-medium text-[var(--text-muted)]">{label}</span>
    <input id={id} className="input" aria-describedby={hint ? `${id}-hint` : undefined} {...input}/>
    {hint && <span id={`${id}-hint`} className="mt-1 block text-[10px] text-[var(--text-muted)]">{hint}</span>}
  </label>;
}

function Submit({ pending, label, pendingLabel }: { pending: boolean; label: string; pendingLabel: string }) {
  return <button disabled={pending} className="h-11 w-full rounded bg-[var(--primary)] px-4 text-sm font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)] disabled:cursor-wait disabled:opacity-60">{pending ? pendingLabel : label}</button>;
}

export function FormMessage({ state }: { state: FormState }) {
  if (!state.message) return null;
  return state.ok
    ? <p role="status" className="rounded border px-3 py-2 text-xs leading-5 text-[var(--positive)]" style={{ borderColor: "var(--positive)", background: "var(--positive-soft)" }}>{state.message}</p>
    : <p role="alert" className="text-xs leading-5 text-[var(--negative)]">{state.message}</p>;
}

export function LoginForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState(loginAction, INITIAL);
  return <form action={action} aria-busy={pending} className="space-y-4">
    <input type="hidden" name="next" value={next}/>
    <fieldset disabled={pending} className="space-y-4 disabled:opacity-60">
      <Field label="E-posta" name="email" type="text" inputMode="email" autoComplete="username" autoCapitalize="none" spellCheck={false} required autoFocus defaultValue={state.values?.email ?? ""}/>
      <Field label="Parola" name="password" type="password" autoComplete="current-password" required aria-invalid={!!state.message && !state.ok}/>
    </fieldset>
    <FormMessage state={state}/>
    {state.code === "email_not_verified" && <p className="text-xs"><Link href="/eposta-dogrula" className="font-medium text-[var(--primary)]">Doğrulama bağlantısını yeniden gönder</Link></p>}
    <Submit pending={pending} label="Giriş yap" pendingLabel="Kontrol ediliyor…"/>
  </form>;
}

export function RegisterForm({ inviteRequired, passwordMinLength }: { inviteRequired: boolean; passwordMinLength: number }) {
  const [state, action, pending] = useActionState(registerAction, INITIAL);
  if (state.ok) return <div className="space-y-4"><FormMessage state={state}/><p className="text-xs leading-5 text-[var(--text-muted)]">E-posta gelmediyse birkaç dakika bekle ya da <Link href="/eposta-dogrula" className="font-medium text-[var(--primary)]">yeniden gönder</Link>.</p></div>;
  return <form action={action} aria-busy={pending} className="space-y-4">
    <fieldset disabled={pending} className="space-y-4 disabled:opacity-60">
      <Field label="E-posta" name="email" type="email" autoComplete="email" autoCapitalize="none" spellCheck={false} required autoFocus defaultValue={state.values?.email ?? ""}/>
      <Field label="Görünen ad (isteğe bağlı)" name="display_name" type="text" autoComplete="nickname" maxLength={64} defaultValue={state.values?.display_name ?? ""}/>
      <Field label="Parola" name="password" type="password" autoComplete="new-password" minLength={passwordMinLength} required hint={`En az ${passwordMinLength} karakter.`}/>
      <Field label="Parola (tekrar)" name="password_confirm" type="password" autoComplete="new-password" minLength={passwordMinLength} required/>
      {inviteRequired && <Field label="Davet kodu" name="invite_code" type="text" autoComplete="off" autoCapitalize="characters" spellCheck={false} required placeholder="XXXX-XXXX-XXXX" defaultValue={state.values?.invite_code ?? ""}/>}
      {/* Bot tuzağı: ekran okuyucu ve klavye için gizli; insanlar doldurmaz. */}
      <div aria-hidden="true" className="absolute -left-[9999px] h-px w-px overflow-hidden"><label>Web siteniz<input name="website" type="text" tabIndex={-1} autoComplete="off"/></label></div>
      <label className="flex items-start gap-2 text-xs leading-5 text-[var(--text-secondary)]">
        <input type="checkbox" name="accept_terms" required className="mt-1"/>
        <span><Link href="/gizlilik" target="_blank" className="font-medium text-[var(--primary)]">Kullanım koşullarını ve aydınlatma metnini</Link> okudum, kabul ediyorum. Platformdaki skorlar ve paper portföyler yatırım tavsiyesi değildir.</span>
      </label>
    </fieldset>
    <FormMessage state={state}/>
    <Submit pending={pending} label="Hesap oluştur" pendingLabel="Gönderiliyor…"/>
  </form>;
}

export function ForgotPasswordForm() {
  const [state, action, pending] = useActionState(requestPasswordResetAction, INITIAL);
  if (state.ok) return <FormMessage state={state}/>;
  return <form action={action} aria-busy={pending} className="space-y-4">
    <fieldset disabled={pending} className="disabled:opacity-60">
      <Field label="E-posta" name="email" type="email" autoComplete="email" autoCapitalize="none" spellCheck={false} required autoFocus defaultValue={state.values?.email ?? ""}/>
    </fieldset>
    <FormMessage state={state}/>
    <Submit pending={pending} label="Sıfırlama bağlantısı gönder" pendingLabel="Gönderiliyor…"/>
  </form>;
}

export function ResetPasswordForm({ token, passwordMinLength }: { token: string; passwordMinLength: number }) {
  const [state, action, pending] = useActionState(resetPasswordAction, INITIAL);
  return <form action={action} aria-busy={pending} className="space-y-4">
    <input type="hidden" name="token" value={token}/>
    <fieldset disabled={pending} className="space-y-4 disabled:opacity-60">
      <Field label="Yeni parola" name="password" type="password" autoComplete="new-password" minLength={passwordMinLength} required autoFocus hint={`En az ${passwordMinLength} karakter. Tüm cihazlardaki oturumlar kapatılır.`}/>
      <Field label="Yeni parola (tekrar)" name="password_confirm" type="password" autoComplete="new-password" minLength={passwordMinLength} required/>
    </fieldset>
    <FormMessage state={state}/>
    {state.code === "invalid_token" && <p className="text-xs"><Link href="/sifremi-unuttum" className="font-medium text-[var(--primary)]">Yeni bağlantı iste</Link></p>}
    <Submit pending={pending} label="Parolayı değiştir" pendingLabel="Kaydediliyor…"/>
  </form>;
}

export function VerifyEmailForm({ token }: { token: string }) {
  const [state, action, pending] = useActionState(verifyEmailAction, INITIAL);
  return <form action={action} aria-busy={pending} className="space-y-4">
    <input type="hidden" name="token" value={token}/>
    <FormMessage state={state}/>
    {state.code === "invalid_token" && <p className="text-xs leading-5 text-[var(--text-muted)]">Bağlantının süresi dolduysa aşağıdan yenisini isteyebilirsin.</p>}
    <Submit pending={pending} label="E-postamı doğrula" pendingLabel="Doğrulanıyor…"/>
  </form>;
}

export function ResendVerificationForm() {
  const [state, action, pending] = useActionState(resendVerificationAction, INITIAL);
  if (state.ok) return <FormMessage state={state}/>;
  return <form action={action} aria-busy={pending} className="space-y-4">
    <fieldset disabled={pending} className="disabled:opacity-60">
      <Field label="Kayıt olduğun e-posta" name="email" type="email" autoComplete="email" autoCapitalize="none" spellCheck={false} required defaultValue={state.values?.email ?? ""}/>
    </fieldset>
    <FormMessage state={state}/>
    <Submit pending={pending} label="Doğrulama bağlantısını gönder" pendingLabel="Gönderiliyor…"/>
  </form>;
}
