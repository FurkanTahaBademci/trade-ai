"use client";

import { useActionState } from "react";
import { loginAction, type LoginState } from "@/app/giris/actions";

export function LoginForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState(loginAction, {} as LoginState);
  return <form action={action} aria-busy={pending} className="space-y-4">
    <input type="hidden" name="next" value={next}/>
    <fieldset disabled={pending} className="space-y-4 disabled:opacity-60">
      <label className="block">
        <span className="mb-1.5 block text-[11px] font-medium text-[var(--text-muted)]">Kullanıcı adı</span>
        <input className="input" name="username" type="text" autoComplete="username" autoCapitalize="none" spellCheck={false} required autoFocus defaultValue={state.username ?? ""}/>
      </label>
      <label className="block">
        <span className="mb-1.5 block text-[11px] font-medium text-[var(--text-muted)]">Parola</span>
        <input className="input" name="password" type="password" autoComplete="current-password" required aria-invalid={!!state.message} aria-describedby={state.message ? "login-error" : undefined}/>
      </label>
    </fieldset>
    {state.message && <p id="login-error" role="alert" className="text-xs text-[var(--negative)]">{state.message}</p>}
    <button disabled={pending} className="h-11 w-full rounded bg-[var(--primary)] px-4 text-sm font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)] disabled:cursor-wait disabled:opacity-60">{pending ? "Kontrol ediliyor…" : "Giriş yap"}</button>
  </form>;
}
