"use server";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import {
  ADMIN_SESSION_COOKIE,
  ADMIN_SESSION_TTL_SECONDS,
  adminConfig,
  createSessionToken,
  safeNextPath,
  verifyCredentials,
} from "@/lib/admin-auth";
import { clearFailures, lockoutRemainingMs, recordFailure, type FailureStore } from "@/lib/login-rate-limit";

export type LoginState = { message?: string; username?: string };

const globalForLogin = globalThis as typeof globalThis & { tradeAiLoginFailures?: FailureStore };
const failures: FailureStore = (globalForLogin.tradeAiLoginFailures ??= new Map());

async function requestContext() {
  const incoming = await headers();
  const client = incoming.get("x-forwarded-for")?.split(",")[0]?.trim() || incoming.get("x-real-ip") || "unknown";
  const secure = incoming.get("x-forwarded-proto")?.split(",")[0]?.trim() === "https";
  return { client, secure };
}

export async function loginAction(_previous: LoginState, formData: FormData): Promise<LoginState> {
  const username = String(formData.get("username") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const next = safeNextPath(formData.get("next"));
  const config = adminConfig();
  if (config.mode === "disabled") redirect(next);
  if (config.mode === "misconfigured") return { username, message: "Yönetici girişi yapılandırılmamış. WEB_ADMIN_PASSWORD ayarlanmalı." };

  const { client, secure } = await requestContext();
  const locked = lockoutRemainingMs(failures, client);
  if (locked > 0) {
    return { username, message: `Çok fazla hatalı deneme. ${Math.ceil(locked / 60000)} dakika sonra tekrar deneyin.` };
  }
  if (!username || !password || !verifyCredentials(username, password)) {
    recordFailure(failures, client);
    await new Promise((resolve) => setTimeout(resolve, 400));
    return { username, message: "Kullanıcı adı veya parola hatalı." };
  }

  clearFailures(failures, client);
  (await cookies()).set(ADMIN_SESSION_COOKIE, createSessionToken(), {
    httpOnly: true,
    secure,
    sameSite: "lax",
    path: "/",
    maxAge: ADMIN_SESSION_TTL_SECONDS,
  });
  redirect(next);
}

export async function logoutAction(): Promise<void> {
  (await cookies()).delete(ADMIN_SESSION_COOKIE);
  redirect("/giris?cikis=1");
}
