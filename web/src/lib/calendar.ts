import type { CalendarEvent, CalendarEventType } from "./types";

export const EVENT_TYPES: { value: CalendarEventType; label: string; tone: string }[] = [
  { value: "PPK", label: "TCMB PPK", tone: "pill-primary" },
  { value: "FINANCIAL_REPORT", label: "Finansal rapor", tone: "" },
  { value: "DIVIDEND", label: "Temettü / kâr payı", tone: "pill-positive" },
  { value: "GENERAL_ASSEMBLY", label: "Genel kurul", tone: "" },
  { value: "CAPITAL_INCREASE", label: "Sermaye artırımı", tone: "pill-negative" },
];

/** `YYYY-MM` biçimini doğrular; geçersizse verilen yedek ayı döndürür. */
export function parseMonth(value: string | undefined, fallback: string): string {
  return value && /^\d{4}-(0[1-9]|1[0-2])$/.test(value) ? value : fallback;
}

export function shiftMonth(month: string, delta: number): string {
  const [year, mon] = month.split("-").map(Number);
  const index = year * 12 + (mon - 1) + delta;
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`;
}

export function monthRange(month: string): { start: string; end: string } {
  const [year, mon] = month.split("-").map(Number);
  const last = new Date(Date.UTC(year, mon, 0)).getUTCDate();
  return { start: `${month}-01`, end: `${month}-${String(last).padStart(2, "0")}` };
}

export function groupByDate(events: CalendarEvent[]): [string, CalendarEvent[]][] {
  const groups = new Map<string, CalendarEvent[]>();
  for (const event of events) groups.set(event.date, [...(groups.get(event.date) ?? []), event]);
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

export function parseTypes(value: string | undefined): CalendarEventType[] {
  const known = new Set<string>(EVENT_TYPES.map((t) => t.value));
  return [...new Set((value ?? "").split(",").filter((item) => known.has(item)))] as CalendarEventType[];
}
