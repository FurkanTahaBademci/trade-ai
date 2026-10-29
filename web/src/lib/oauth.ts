/**
 * Google ile giriş akışının saf yardımcıları. Yetki isteği sırasında `state`,
 * PKCE doğrulayıcısı ve `nonce` kısa ömürlü HttpOnly çerezde tutulur; geri
 * dönüşte (`/giris/google/callback`) çerezle karşılaştırılıp silinir. Hata
 * kodları URL'de yalnız sabit kod olarak taşınır, mesaj metni sayfada seçilir.
 */

export const OAUTH_COOKIE = "tradeai_oauth";
export const OAUTH_COOKIE_PATH = "/giris/google";
export const OAUTH_COOKIE_MAX_AGE = 10 * 60;

export type GoogleMode = "login" | "signup" | "link";
export type OAuthState = { state: string; verifier: string; nonce: string; mode: GoogleMode; next: string; invite: string; terms: boolean };

const MODES: readonly GoogleMode[] = ["login", "signup", "link"];

export function parseGoogleMode(value: unknown): GoogleMode {
  return MODES.includes(value as GoogleMode) ? (value as GoogleMode) : "login";
}

export function encodeOAuthState(value: OAuthState): string {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

export function decodeOAuthState(raw: string | undefined): OAuthState | null {
  if (!raw || raw.length > 4096) return null;
  try {
    const value = JSON.parse(Buffer.from(raw, "base64url").toString("utf8")) as Partial<OAuthState>;
    const strings = [value.state, value.verifier, value.nonce, value.next, value.invite];
    if (!strings.every((item) => typeof item === "string") || !value.state || !value.verifier || !value.nonce) return null;
    return { ...(value as OAuthState), mode: parseGoogleMode(value.mode), terms: value.terms === true };
  } catch {
    return null;
  }
}

export const GOOGLE_MESSAGES: Record<string, string> = {
  cancelled: "Google girişi iptal edildi.",
  state: "Google oturumu doğrulanamadı ya da süresi doldu. Tekrar dene.",
  google_failed: "Google girişi tamamlanamadı. Lütfen tekrar dene.",
  google_email_unverified: "Google hesabının e-posta adresi doğrulanmamış; bu hesapla giriş yapılamaz.",
  google_disabled: "Google ile giriş şu an etkin değil.",
  link_required: "Bu e-postayla kayıtlı bir hesap var. Parolanla giriş yapıp Hesabım sayfasından Google hesabını bağlayabilirsin.",
  signup_required: "Bu Google hesabıyla kayıtlı bir hesap yok. Koşulları onaylayıp “Google ile kayıt ol” düğmesini kullan.",
  terms_required: "Google ile kayıt olmak için koşulları onaylamalısın.",
  invalid_invite: "Davet kodu geçersiz, süresi dolmuş ya da kullanılmış.",
  registration_closed: "Yeni kayıtlar şu an kapalı.",
  account_disabled: "Bu hesap devre dışı bırakılmış.",
  identity_in_use: "Bu Google hesabı başka bir trade-ai hesabına bağlı.",
  already_linked: "Hesabına zaten başka bir Google hesabı bağlı; önce onu kaldır.",
  rate_limited: "Çok fazla deneme yapıldı. Biraz sonra tekrar dene.",
  unavailable: "Hesap servisine şu an ulaşılamıyor. Biraz sonra tekrar dene.",
};

export function googleMessage(code: string | undefined): string | undefined {
  if (!code) return undefined;
  return GOOGLE_MESSAGES[code] ?? GOOGLE_MESSAGES.google_failed;
}

const SIGNUP_CODES = new Set(["signup_required", "terms_required", "invalid_invite", "registration_closed"]);

/** Hata kodunun gösterileceği sayfa: bağlama → Hesabım, kayıt sorunları → Kayıt, diğerleri → Giriş. */
export function googleErrorPath(mode: GoogleMode, code: string): string {
  if (mode === "link") return `/hesap?result=error&message=${encodeURIComponent(googleMessage(code) ?? "")}`;
  const page = mode === "signup" || SIGNUP_CODES.has(code) ? "/kayit" : "/giris";
  return `${page}?google=${encodeURIComponent(code)}`;
}
