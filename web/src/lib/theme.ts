/**
 * TradeAI Koyu ve Açık Tema (Dark & Light Mode) Yönetimi.
 */

export type Theme = "dark" | "light" | "system";

export const THEME_STORAGE_KEY = "trade-ai:theme";

/**
 * Kullanıcı tercihi ve sistem durumuna göre nihai temayı (dark/light) belirler.
 */
export function resolveTheme(
  preference: Theme | string | null | undefined,
  systemPrefersDark = true,
): "dark" | "light" {
  if (preference === "light") return "light";
  if (preference === "dark") return "dark";
  return systemPrefersDark ? "dark" : "light";
}

/**
 * LocalStorage üzerindeki kayıtlı temayı döner, yoksa "system" kabul eder.
 */
export function getStoredTheme(): Theme {
  if (typeof window === "undefined") return "system";
  try {
    const item = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (item === "light" || item === "dark" || item === "system") {
      return item;
    }
  } catch {
    // localStorage erişim hatası (gizli sekme vb.)
  }
  return "system";
}

/**
 * Temayı DOM'a ve localStorage'a uygular.
 */
export function applyTheme(theme: Theme): "dark" | "light" {
  if (typeof window === "undefined") return "dark";

  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // ignore
  }

  const systemPrefersDark =
    typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
      : true;

  const resolved = resolveTheme(theme, systemPrefersDark);
  document.documentElement.setAttribute("data-theme", resolved);

  // Tema değişikliğini dinleyen bileşenleri bilgilendir
  try {
    window.dispatchEvent(
      new CustomEvent("trade-ai:theme-change", { detail: { theme, resolved } }),
    );
  } catch {
    // ignore
  }

  return resolved;
}
