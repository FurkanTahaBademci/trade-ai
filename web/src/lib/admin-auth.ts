import { createHash, createHmac, timingSafeEqual } from "node:crypto";

/**
 * Yönetim girişi: /giris formu doğrular, imzalı ve süreli bir oturum çerezi
 * verir. Çerez yalnız `kullanıcı + bitiş zamanı` taşır; imza anahtarı
 * yapılandırılmış paroladan türetilir, bu yüzden parola değişince tüm açık
 * oturumlar geçersiz olur. Ayrıntı: docs/ADMIN.md
 */

export type AdminAuthState = "disabled" | "misconfigured" | "authorized" | "unauthorized";

export type AuthEnvironment = {
  NODE_ENV?: string;
  WEB_ADMIN_USERNAME?: string;
  WEB_ADMIN_PASSWORD?: string;
  ADMIN_API_TOKEN?: string;
};

export const ADMIN_SESSION_COOKIE = "tradeai_admin";
export const ADMIN_SESSION_TTL_SECONDS = 12 * 60 * 60;
export const DEFAULT_ADMIN_REDIRECT = "/sistem";

type AdminConfig =
  | { mode: "disabled" }
  | { mode: "misconfigured" }
  | { mode: "enabled"; username: string; password: string };

function safeEqual(left: string, right: string): boolean {
  // Uzunluk farkını da sabit sürede karşılaştırmak için önce özetle.
  const leftDigest = createHash("sha256").update(left).digest();
  const rightDigest = createHash("sha256").update(right).digest();
  return timingSafeEqual(leftDigest, rightDigest) && left.length === right.length;
}

export function adminConfig(env: AuthEnvironment = process.env): AdminConfig {
  const explicitlyConfigured = Boolean(env.WEB_ADMIN_PASSWORD);
  // Geliştirme sunucusunda (`npm run dev`) parola verilmediyse giriş kapalıdır.
  // Docker imajı her zaman NODE_ENV=production ile çalışır.
  if (env.NODE_ENV !== "production" && !explicitlyConfigured) return { mode: "disabled" };
  const password = env.WEB_ADMIN_PASSWORD || env.ADMIN_API_TOKEN;
  if (!password) return { mode: "misconfigured" };
  return { mode: "enabled", username: env.WEB_ADMIN_USERNAME || "admin", password };
}

export function verifyCredentials(username: string, password: string, env: AuthEnvironment = process.env): boolean {
  const config = adminConfig(env);
  if (config.mode !== "enabled") return false;
  const usernameMatches = safeEqual(username, config.username);
  const passwordMatches = safeEqual(password, config.password);
  return usernameMatches && passwordMatches;
}

function signingKey(config: { username: string; password: string }): Buffer {
  return createHash("sha256").update(`trade-ai-admin-session\0${config.username}\0${config.password}`).digest();
}

function sign(payload: string, key: Buffer): string {
  return createHmac("sha256", key).update(payload).digest("base64url");
}

export function createSessionToken(env: AuthEnvironment = process.env, nowMs: number = Date.now()): string {
  const config = adminConfig(env);
  if (config.mode !== "enabled") throw new Error("Yönetici girişi etkin değil");
  const payload = Buffer.from(JSON.stringify({
    u: config.username,
    exp: Math.floor(nowMs / 1000) + ADMIN_SESSION_TTL_SECONDS,
  })).toString("base64url");
  return `${payload}.${sign(payload, signingKey(config))}`;
}

export function verifySessionToken(token: string | undefined, env: AuthEnvironment = process.env, nowMs: number = Date.now()): boolean {
  const config = adminConfig(env);
  if (config.mode !== "enabled" || !token) return false;
  const [payload, signature, extra] = token.split(".");
  if (!payload || !signature || extra !== undefined) return false;
  if (!safeEqual(signature, sign(payload, signingKey(config)))) return false;
  try {
    const data = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as { u?: unknown; exp?: unknown };
    return data.u === config.username && typeof data.exp === "number" && data.exp > Math.floor(nowMs / 1000);
  } catch {
    return false;
  }
}

export function adminAuthState(sessionToken: string | undefined, env: AuthEnvironment = process.env, nowMs: number = Date.now()): AdminAuthState {
  const config = adminConfig(env);
  if (config.mode === "disabled") return "disabled";
  if (config.mode === "misconfigured") return "misconfigured";
  return verifySessionToken(sessionToken, env, nowMs) ? "authorized" : "unauthorized";
}

/** Girişten sonra yalnız site içi bir yola dön (açık yönlendirmeyi engeller). */
export function safeNextPath(value: unknown): string {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return DEFAULT_ADMIN_REDIRECT;
  }
  try {
    const url = new URL(value, "http://local");
    if (url.origin !== "http://local" || url.pathname.startsWith("/giris")) return DEFAULT_ADMIN_REDIRECT;
    return `${url.pathname}${url.search}`;
  } catch {
    return DEFAULT_ADMIN_REDIRECT;
  }
}
