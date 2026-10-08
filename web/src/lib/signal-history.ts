import { extractChartDate } from "./chart-data";
import type { SignalHistoryPoint } from "./types";

export const COMPONENT_KEYS = ["llm", "fundamental", "analyst", "fund_flow"] as const;

// Gecersiz/yinelenen gunleri eler, eskiden yeniye dizer.
export function normalizeHistory(source: SignalHistoryPoint[]): SignalHistoryPoint[] {
  if (!Array.isArray(source)) return [];
  const rows = new Map<string, SignalHistoryPoint>();
  for (const row of source) {
    const date = row ? extractChartDate(row.as_of_date) : null;
    const score = row ? Number(row.composite_score) : NaN;
    if (!date || !Number.isFinite(score)) continue;
    rows.set(date, { ...row, as_of_date: date, composite_score: score });
  }
  return [...rows.values()].sort((a, b) => a.as_of_date.localeCompare(b.as_of_date));
}

// Son noktanin, `days` gun onceki (veya ondan onceki en yakin) noktaya farki.
export function scoreDelta(points: SignalHistoryPoint[], days: number): number | null {
  if (points.length < 2) return null;
  const last = points[points.length - 1];
  const cutoff = Date.parse(`${last.as_of_date}T00:00:00Z`) - days * 86_400_000;
  let base: SignalHistoryPoint | null = null;
  for (const point of points) {
    if (Date.parse(`${point.as_of_date}T00:00:00Z`) <= cutoff) base = point;
    else break;
  }
  return base ? last.composite_score - base.composite_score : null;
}

export type LabelChange = { date: string; from: string; to: string; score: number; index: number };

export function labelChanges(points: SignalHistoryPoint[]): LabelChange[] {
  const changes: LabelChange[] = [];
  for (let i = 1; i < points.length; i++) {
    if (points[i].signal_label !== points[i - 1].signal_label) {
      changes.push({ date: points[i].as_of_date, from: points[i - 1].signal_label, to: points[i].signal_label, score: points[i].composite_score, index: i });
    }
  }
  return changes;
}

export function componentSeries(points: SignalHistoryPoint[], key: string): Array<number | null> {
  return points.map((point) => {
    const value = point.component_scores?.[key];
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  });
}

export function driverKindName(kind: string): string {
  return ({ news: "Haber", kap: "KAP", analyst: "Analist" } as Record<string, string>)[kind] ?? kind;
}
