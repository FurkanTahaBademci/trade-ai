export function formatDate(value: string, withTime = false) {
  const date = new Date(value); if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("tr-TR", withTime ? { timeZone: "Europe/Istanbul", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" } : { timeZone: "Europe/Istanbul", day: "2-digit", month: "short", year: "numeric" }).format(date);
}
export function relativeTime(value: string) {
  const date = new Date(value).getTime(); if (Number.isNaN(date)) return "—";
  const diff = date - Date.now(); const abs = Math.abs(diff); const formatter = new Intl.RelativeTimeFormat("tr", { numeric: "auto" });
  if (abs < 3_600_000) return formatter.format(Math.round(diff / 60_000), "minute");
  if (abs < 86_400_000) return formatter.format(Math.round(diff / 3_600_000), "hour");
  return formatter.format(Math.round(diff / 86_400_000), "day");
}
export function formatNumber(value: number | null | undefined, digits = 1) { return value == null || !Number.isFinite(value) ? "—" : new Intl.NumberFormat("tr-TR", { maximumFractionDigits: digits }).format(value); }
// Kısaltmalı tutarlar sabit tek ondalıkla yazılır ("₺7,9 Tn" ile "₺8,0 Tn" aynı seride
// tutarlı dursun). Intl'in Türkçe "B" (bin) kısaltması İngilizce billion ile
// karıştığı için "Bin" olarak açılır.
const COMPACT_MONEY = new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY", notation: "compact", minimumFractionDigits: 1, maximumFractionDigits: 1 });
const SMALL_MONEY = new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY", maximumFractionDigits: 0 });
const STANDARD_MONEY = new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY", minimumFractionDigits: 2, maximumFractionDigits: 2 });
export function formatMoney(value: number | null | undefined, compact = false) {
  if (value == null || !Number.isFinite(value)) return "—";
  if (!compact) return STANDARD_MONEY.format(value);
  const parts = COMPACT_MONEY.formatToParts(value);
  if (!parts.some((part) => part.type === "compact")) return SMALL_MONEY.format(value);
  return parts.map((part) => part.type === "compact" && part.value === "B" ? "Bin" : part.value).join("");
}
/** Türkçe yüzde: "%41,5", "-%3,0", işaretli "+%4,6". Ondalık sayısı sabittir (varsayılan 1). */
export function formatPercent(value: number | null | undefined, signed = false, digits = 1) {
  if (value == null || !Number.isFinite(value)) return "—";
  const factor = 10 ** digits;
  const rounded = Math.round(Math.abs(value) * factor) / factor;
  const body = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(rounded);
  const sign = rounded === 0 ? "" : value < 0 ? "-" : signed ? "+" : "";
  return `${sign}%${body}`;
}
export function formatBytes(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value) || value < 0) return "—";
  if (value === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(units.length - 1, Math.floor(Math.log(value) / Math.log(1024)));
  return `${new Intl.NumberFormat("tr-TR", { maximumFractionDigits: exponent === 0 ? 0 : 1 }).format(value / 1024 ** exponent)} ${units[exponent]}`;
}
export function sourceName(source: string) { const names: Record<string, string> = { bloomberght: "Bloomberg HT", investing_tr: "Investing", aa_ekonomi: "AA Ekonomi", dunya: "Dünya Gazetesi", foreks: "Foreks", trthaber: "TRT Haber", news: "Haber", kap: "KAP" }; return names[source] ?? source; }
export function eventName(event: string | null) { const names: Record<string, string> = { earnings: "Finansal sonuç", corporate_action: "Kurumsal aksiyon", contract: "Sözleşme", financing: "Finansman", governance: "Yönetim", regulatory: "Düzenleme", macro: "Makro", market: "Piyasa", legal: "Hukuk", operations: "Operasyon", other: "Diğer" }; return event ? names[event] ?? event : "Genel"; }
export function signalName(value: string) { const names: Record<string, string> = { VERY_POSITIVE: "Çok pozitif", POSITIVE: "Pozitif", NEUTRAL: "Nötr", NEGATIVE: "Negatif", VERY_NEGATIVE: "Çok negatif" }; return names[value] ?? value; }
export function componentName(value: string) { const names: Record<string, string> = { llm: "AI etkisi", fundamental: "Temel analiz", analyst: "Analist görüşü", momentum: "Momentum (BIST100'e göre)", fund_flow: "Fon akımı" }; return names[value] ?? value; }
