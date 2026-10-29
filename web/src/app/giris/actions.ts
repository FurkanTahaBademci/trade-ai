"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import {
  ADMIN_SESSION_COOKIE,
  ADMIN_SESSION_TTL_SECONDS,
  adminConfig,
  createSessionToken,
  DEFAULT_ADMIN_REDIRECT,
  safeNextPath,
  verifyCredentials,
} from "@/lib/admin-auth";
import { type Account, SESSION_COOKIE } from "@/lib/account";
import { accountRequest, requestContext, serviceRequest, sessionToken, setSessionCookie } from "@/lib/account-server";
import { encodeOAuthState, googleErrorPath, OAUTH_COOKIE, OAUTH_COOKIE_MAX_AGE, OAUTH_COOKIE_PATH, type OAuthState, parseGoogleMode } from "@/lib/oauth";
import { clearFailures, lockoutRemainingMs, recordFailure, type FailureStore } from "@/lib/login-rate-limit";

/** Hesap formlarının ortak durumu (useActionState). */
export type FormState = { ok?: boolean; message?: string; code?: string; values?: Record<string, string> };

const globalForLogin = globalThis as typeof globalThis & { tradeAiLoginFailures?: FailureStore };
const failures: FailureStore = (globalForLogin.tradeAiLoginFailures ??= new Map());
// server-cluster.cjs her sürece gerçek süreç sayısını WEB_WORKERS olarak verir.
const processes = Number(process.env.WEB_WORKERS) || 1;

function text(formData: FormData, name: string): string {
  return String(formData.get(name) ?? "");
}

/** Ortam değişkeniyle tanımlı tek yönetici hesabı (kullanıcı adı + parola). */
async function environmentAdminLogin(username: string, password: string, next: unknown): Promise<FormState> {
  const config = adminConfig();
  if (config.mode === "disabled") redirect(safeNextPath(next, DEFAULT_ADMIN_REDIRECT));
  if (config.mode === "misconfigured") return { message: "Yönetici girişi yapılandırılmamış. WEB_ADMIN_PASSWORD ayarlanmalı.", values: { email: username } };

  const { clientIp, secure } = await requestContext();
  const locked = lockoutRemainingMs(failures, clientIp, Date.now(), processes);
  if (locked > 0) return { message: `Çok fazla hatalı deneme. ${Math.ceil(locked / 60000)} dakika sonra tekrar dene.`, values: { email: username } };
  if (!verifyCredentials(username, password)) {
    recordFailure(failures, clientIp);
    await new Promise((resolve) => setTimeout(resolve, 400));
    return { message: "Kullanıcı adı veya parola hatalı.", values: { email: username } };
  }
  clearFailures(failures, clientIp);
  (await cookies()).set(ADMIN_SESSION_COOKIE, createSessionToken(), {
    httpOnly: true,
    secure,
    sameSite: "lax",
    path: "/",
    maxAge: ADMIN_SESSION_TTL_SECONDS,
  });
  redirect(safeNextPath(next, DEFAULT_ADMIN_REDIRECT));
}

export async function loginAction(_previous: FormState, formData: FormData): Promise<FormState> {
  const identifier = text(formData, "email").trim();
  const password = text(formData, "password");
  const next = formData.get("next");
  if (!identifier || !password) return { message: "E-posta adresini ve parolanı gir.", values: { email: identifier } };
  // "@" içermeyen giriş, ortam değişkenindeki yönetici kullanıcı adıdır.
  if (!identifier.includes("@")) return environmentAdminLogin(identifier, password, next);

  const { clientIp, userAgent, secure } = await requestContext();
  const result = await serviceRequest<{ token: string; expires_at: string; user: Account }>("/api/auth/login", {
    body: { email: identifier, password, client_ip: clientIp, user_agent: userAgent },
  });
  if (!result.ok) return { message: result.message, code: result.code, values: { email: identifier } };
  await setSessionCookie(result.data.token, result.data.expires_at, secure);
  redirect(safeNextPath(next, result.data.user.role === "admin" ? DEFAULT_ADMIN_REDIRECT : "/"));
}

export async function logoutAction(): Promise<void> {
  const store = await cookies();
  store.delete(ADMIN_SESSION_COOKIE);
  const token = store.get(SESSION_COOKIE)?.value;
  if (token) {
    // API'de oturum silinemese de çerez kaldırılır; oturum süresi dolunca temizlenir.
    await accountRequest("/api/me/logout", token, { method: "POST" });
    store.delete(SESSION_COOKIE);
  }
  redirect("/giris?cikis=1");
}

export async function registerAction(_previous: FormState, formData: FormData): Promise<FormState> {
  const values = { email: text(formData, "email").trim(), display_name: text(formData, "display_name").trim(), invite_code: text(formData, "invite_code").trim() };
  const accepted = { ok: true, message: "Doğrulama bağlantısını e-posta adresine gönderdik. Hesabını etkinleştirmek için gelen kutunu (ve gereksiz klasörünü) kontrol et." };
  // Botlar gizli alanı doldurur; gerçek kayıtla aynı yanıtı alır ama hesap açılmaz.
  if (text(formData, "website")) return accepted;
  const password = text(formData, "password");
  if (password !== text(formData, "password_confirm")) return { message: "Parolalar eşleşmiyor.", values };

  const { clientIp, userAgent } = await requestContext();
  const result = await serviceRequest<{ message: string }>("/api/auth/register", {
    body: { ...values, password, accept_terms: formData.get("accept_terms") === "on", client_ip: clientIp, user_agent: userAgent },
  });
  if (!result.ok) return { message: result.message, code: result.code, values };
  return { ok: true, message: result.data.message };
}

export async function requestPasswordResetAction(_previous: FormState, formData: FormData): Promise<FormState> {
  const email = text(formData, "email").trim();
  const { clientIp } = await requestContext();
  const result = await serviceRequest<{ message: string }>("/api/auth/password-reset/request", { body: { email, client_ip: clientIp } });
  if (!result.ok) return { message: result.message, code: result.code, values: { email } };
  return { ok: true, message: result.data.message };
}

export async function resetPasswordAction(_previous: FormState, formData: FormData): Promise<FormState> {
  const token = text(formData, "token");
  const password = text(formData, "password");
  if (password !== text(formData, "password_confirm")) return { message: "Parolalar eşleşmiyor." };
  const { clientIp } = await requestContext();
  const result = await serviceRequest("/api/auth/password-reset/confirm", { body: { token, password, client_ip: clientIp } });
  if (!result.ok) return { message: result.message, code: result.code };
  redirect("/giris?sifirlandi=1");
}

export async function verifyEmailAction(_previous: FormState, formData: FormData): Promise<FormState> {
  const { clientIp } = await requestContext();
  const result = await serviceRequest("/api/auth/verify-email", { body: { token: text(formData, "token"), client_ip: clientIp } });
  if (!result.ok) return { message: result.message, code: result.code };
  redirect("/giris?dogrulandi=1");
}

export async function resendVerificationAction(_previous: FormState, formData: FormData): Promise<FormState> {
  const email = text(formData, "email").trim();
  const { clientIp } = await requestContext();
  const result = await serviceRequest<{ message: string }>("/api/auth/resend-verification", { body: { email, client_ip: clientIp } });
  if (!result.ok) return { message: result.message, code: result.code, values: { email } };
  return { ok: true, message: result.data.message };
}

/** Google yetki sayfasına gönderir; dönüşü `/giris/google/callback` karşılar. */
export async function startGoogleAction(formData: FormData): Promise<void> {
  const mode = parseGoogleMode(formData.get("mode"));
  const terms = formData.get("accept_terms") === "on";
  if (mode === "signup" && !terms) redirect(googleErrorPath(mode, "terms_required"));
  if (mode === "link" && !(await sessionToken())) redirect("/giris?next=/hesap");
  const started = await serviceRequest<{ url: string; state: string; code_verifier: string; nonce: string }>("/api/auth/google/start", { method: "POST" });
  if (!started.ok) redirect(googleErrorPath(mode, started.code ?? "unavailable"));
  const { secure } = await requestContext();
  const state: OAuthState = {
    state: started.data.state,
    verifier: started.data.code_verifier,
    nonce: started.data.nonce,
    mode,
    next: safeNextPath(formData.get("next"), ""),
    invite: text(formData, "invite_code").trim().slice(0, 64),
    terms,
  };
  (await cookies()).set(OAUTH_COOKIE, encodeOAuthState(state), {
    httpOnly: true,
    secure,
    // Google'dan dönüş üst düzey GET gezinmesi; Lax çerez gönderilir.
    sameSite: "lax",
    path: OAUTH_COOKIE_PATH,
    maxAge: OAUTH_COOKIE_MAX_AGE,
  });
  redirect(started.data.url);
}
