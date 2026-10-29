/**
 * Kullanıcı hesapları için ortak tipler ve saf yardımcılar. Sunucu tarafı
 * istekleri `account-server.ts`, proxy'deki oturum denetimi `fetchAccountState`
 * kullanır. Oturum token'ı yalnız HttpOnly çerezde durur ve API'ye
 * `Authorization: Bearer` ile iletilir; kişisel yanıtlar asla önbelleğe alınmaz.
 */

export const SESSION_COOKIE = "tradeai_session";

export type Account = {
  id: number;
  email: string;
  display_name: string;
  role: "user" | "admin";
  email_verified: boolean;
  created_at: string | null;
  last_login_at: string | null;
};

/** Kabuk (AppShell) için yeterli, istemciye giden en küçük hesap bilgisi. */
export type AccountSummary = Pick<Account, "display_name" | "email" | "role">;

export type AccountApiFailure = { ok: false; status: number; code?: string; message: string };
export type AccountApiResult<T> = { ok: true; status: number; data: T } | AccountApiFailure;

export const SERVICE_UNAVAILABLE_MESSAGE = "Hesap servisine şu an ulaşılamıyor. Biraz sonra tekrar dene.";

function fallbackMessage(status: number): string {
  if (status === 429) return "Çok fazla deneme yapıldı. Biraz sonra tekrar dene.";
  if (status >= 500) return SERVICE_UNAVAILABLE_MESSAGE;
  if (status === 422) return "Gönderilen bilgiler geçersiz.";
  return "İşlem tamamlanamadı.";
}

/** API hata gövdesi: `{detail: {code, message}}`, `{detail: "..."}` ya da FastAPI doğrulama listesi. */
export function parseApiError(payload: unknown, status: number): AccountApiFailure {
  const detail = payload && typeof payload === "object" ? (payload as { detail?: unknown }).detail : undefined;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const { code, message } = detail as { code?: unknown; message?: unknown };
    return { ok: false, status, code: typeof code === "string" ? code : undefined, message: typeof message === "string" && message ? message : fallbackMessage(status) };
  }
  if (typeof detail === "string" && detail) return { ok: false, status, message: detail };
  return { ok: false, status, message: fallbackMessage(status) };
}

/** Kişisel ve yönetim uçları paylaşılan `apiGet` önbelleğinden asla geçmemeli. */
export function isPrivateApiPath(path: string): boolean {
  return /^\/api\/(me|auth|admin)(\/|\?|$)/.test(path);
}

export function accountInitials(account: { display_name: string; email: string }): string {
  const source = account.display_name.trim() || account.email;
  const words = source.split(/[\s@._-]+/).filter(Boolean);
  const letters = words.length > 1 ? words[0][0] + words[1][0] : (words[0] ?? "?").slice(0, 2);
  return letters.toLocaleUpperCase("tr-TR");
}

/** Çerez ömrü oturumun bitişine eşit; geçersiz tarihte 30 gün. */
export function sessionCookieMaxAge(expiresAt: string, nowMs: number = Date.now()): number {
  const expires = Date.parse(expiresAt);
  const seconds = Number.isFinite(expires) ? Math.floor((expires - nowMs) / 1000) : 30 * 24 * 60 * 60;
  return Math.max(0, Math.min(seconds, 365 * 24 * 60 * 60));
}

/** Oturum listesinde gösterilecek kısa cihaz adı. */
export function describeUserAgent(userAgent: string | null): string {
  if (!userAgent) return "Bilinmeyen cihaz";
  const browser = /Edg\//.test(userAgent) ? "Edge" : /OPR\//.test(userAgent) ? "Opera" : /Firefox\//.test(userAgent) ? "Firefox" : /Chrome\//.test(userAgent) ? "Chrome" : /Safari\//.test(userAgent) ? "Safari" : "Tarayıcı";
  const system = /iPhone|iPad/.test(userAgent) ? "iOS" : /Android/.test(userAgent) ? "Android" : /Windows/.test(userAgent) ? "Windows" : /Mac OS X/.test(userAgent) ? "macOS" : /Linux/.test(userAgent) ? "Linux" : "";
  return system ? `${browser} · ${system}` : browser;
}

export type AccountState = { state: "valid"; account: Account } | { state: "invalid" } | { state: "error" };

/**
 * Oturum token'ını API'de doğrular. "invalid" çerezin silinebileceğini,
 * "error" ise API'ye ulaşılamadığını (çerez korunur) söyler.
 */
export async function fetchAccountState(token: string, apiBase: string): Promise<AccountState> {
  try {
    const response = await fetch(`${apiBase}/api/me`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(5_000),
    });
    if (response.status === 401) return { state: "invalid" };
    if (!response.ok) return { state: "error" };
    return { state: "valid", account: (await response.json()) as Account };
  } catch {
    return { state: "error" };
  }
}
