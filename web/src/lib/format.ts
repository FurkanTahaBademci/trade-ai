export function formatDate(value: string, withTime = false) {
  const date = new Date(value); if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("tr-TR", withTime ? { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" } : { day: "2-digit", month: "short", year: "numeric" }).format(date);
}
export function relativeTime(value: string) {
  const date = new Date(value).getTime(); if (Number.isNaN(date)) return "—";
  const diff = date - Date.now(); const abs = Math.abs(diff); const formatter = new Intl.RelativeTimeFormat("tr", { numeric: "auto" });
  if (abs < 3_600_000) return formatter.format(Math.round(diff / 60_000), "minute");
  if (abs < 86_400_000) return formatter.format(Math.round(diff / 3_600_000), "hour");
  return formatter.format(Math.round(diff / 86_400_000), "day");
}
export function formatNumber(value: number | null | undefined, digits = 1) { return value == null || !Number.isFinite(value) ? "—" : new Intl.NumberFormat("tr-TR", { maximumFractionDigits: digits }).format(value); }
export function formatMoney(value: number | null | undefined, compact = false) { return value == null || !Number.isFinite(value) ? "—" : new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY", notation: compact ? "compact" : "standard", maximumFractionDigits: compact ? 1 : 2 }).format(value); }
export function formatPercent(value: number | null | undefined, signed = false) { return value == null || !Number.isFinite(value) ? "—" : `${signed && value > 0 ? "+" : ""}${new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 }).format(value)}%`; }
export function sourceName(source: string) { const names: Record<string, string> = { bloomberght: "Bloomberg HT", investing_tr: "Investing", aa_ekonomi: "AA Ekonomi", dunya: "Dünya Gazetesi", foreks: "Foreks", news: "Haber", kap: "KAP" }; return names[source] ?? source; }
export function eventName(event: string | null) { const names: Record<string, string> = { earnings: "Finansal sonuç", corporate_action: "Kurumsal aksiyon", contract: "Sözleşme", financing: "Finansman", governance: "Yönetim", regulatory: "Düzenleme", macro: "Makro", market: "Piyasa", legal: "Hukuk", operations: "Operasyon", other: "Diğer" }; return event ? names[event] ?? event : "Genel"; }
export function signalName(value: string) { const names: Record<string, string> = { VERY_POSITIVE: "Çok pozitif", POSITIVE: "Pozitif", NEUTRAL: "Nötr", NEGATIVE: "Negatif", VERY_NEGATIVE: "Çok negatif" }; return names[value] ?? value; }
export function componentName(value: string) { const names: Record<string, string> = { llm: "AI etkisi", fundamental: "Temel analiz", analyst: "Analist görüşü", fund_flow: "Fon akımı" }; return names[value] ?? value; }
