import "server-only";

import { cookies, headers } from "next/headers";
import { cache } from "react";
import {
  type Account,
  type AccountApiResult,
  fetchAccountState,
  parseApiError,
  SERVICE_UNAVAILABLE_MESSAGE,
  SESSION_COOKIE,
  sessionCookieMaxAge,
} from "./account";

export function apiBase(): string {
  return process.env.API_INTERNAL_URL ?? "http://localhost:8000";
}

async function call<T>(path: string, init: RequestInit, extraHeaders: Record<string, string>): Promise<AccountApiResult<T>> {
  try {
    const response = await fetch(`${apiBase()}${path}`, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
      headers: { "Content-Type": "application/json", ...extraHeaders },
    });
    if (response.status === 204) return { ok: true, status: 204, data: undefined as T };
    const payload: unknown = await response.json().catch(() => null);
    return response.ok ? { ok: true, status: response.status, data: payload as T } : parseApiError(payload, response.status);
  } catch {
    return { ok: false, status: 503, message: SERVICE_UNAVAILABLE_MESSAGE };
  }
}

/** Servis anahtarıyla çağrı: `/api/auth/*` ve yönetici uçları (`/api/admin/*`). */
export function serviceRequest<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<AccountApiResult<T>> {
  const method = options.method ?? (options.body === undefined ? "GET" : "POST");
  return call<T>(path, { method, body: options.body === undefined ? undefined : JSON.stringify(options.body) }, { "X-Admin-Token": process.env.ADMIN_API_TOKEN ?? "" });
}

/** Oturumlu kullanıcının kendi uçları (`/api/me/*`). */
export function accountRequest<T>(path: string, token: string, options: { method?: string; body?: unknown } = {}): Promise<AccountApiResult<T>> {
  const method = options.method ?? (options.body === undefined ? "GET" : "POST");
  return call<T>(path, { method, body: options.body === undefined ? undefined : JSON.stringify(options.body) }, { Authorization: `Bearer ${token}` });
}

export async function sessionToken(): Promise<string | undefined> {
  return (await cookies()).get(SESSION_COOKIE)?.value || undefined;
}

/** İstek başına bir kez çözülür (layout, sayfa ve action aynı sonucu paylaşır). */
export const currentAccount = cache(async (): Promise<Account | null> => {
  const token = await sessionToken();
  if (!token) return null;
  const result = await fetchAccountState(token, apiBase());
  return result.state === "valid" ? result.account : null;
});

/** İstemci IP'si, tarayıcı kimliği ve HTTPS bilgisi (proxy başlıklarından). */
export async function requestContext() {
  const incoming = await headers();
  const clientIp = incoming.get("x-forwarded-for")?.split(",")[0]?.trim() || incoming.get("x-real-ip") || "unknown";
  const secure = incoming.get("x-forwarded-proto")?.split(",")[0]?.trim() === "https";
  return { clientIp: clientIp.slice(0, 64), userAgent: (incoming.get("user-agent") ?? "").slice(0, 512), secure };
}

export async function setSessionCookie(token: string, expiresAt: string, secure: boolean): Promise<void> {
  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure,
    sameSite: "lax",
    path: "/",
    maxAge: sessionCookieMaxAge(expiresAt),
  });
}

export async function clearSessionCookie(): Promise<void> {
  (await cookies()).delete(SESSION_COOKIE);
}
