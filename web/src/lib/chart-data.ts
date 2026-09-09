import type { Price } from "./types";

export function extractChartDate(value: unknown): string | null {
  if (value == null) return null;
  let str: string;
  if (value instanceof Date) {
    if (!Number.isFinite(value.getTime())) return null;
    str = value.toISOString().slice(0, 10);
  } else if (typeof value === "string") {
    str = value.trim().slice(0, 10);
  } else {
    return null;
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(str)) return null;
  const timestamp = Date.parse(`${str}T00:00:00Z`);
  if (!Number.isFinite(timestamp)) return null;
  if (new Date(timestamp).toISOString().slice(0, 10) !== str) return null;
  return str;
}

export function validChartDate(value: unknown): boolean {
  return extractChartDate(value) != null;
}

function parseNumber(value: unknown): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string") {
    const parsed = parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function parsePositive(value: unknown): number | null {
  const num = parseNumber(value);
  return num != null && num > 0 ? num : null;
}

export function normalizePrices(source: Price[]): Price[] {
  if (!Array.isArray(source)) return [];
  const rows = new Map<string, Price>();
  for (const row of source) {
    if (!row) continue;
    const cleanDate = extractChartDate(row.date);
    const close = parsePositive(row.close);
    if (!cleanDate || close == null) continue;

    const rawLow = parsePositive(row.low);
    const rawHigh = parsePositive(row.high);
    const low = rawLow != null && rawLow <= close ? rawLow : null;
    const high = rawHigh != null && rawHigh >= close ? rawHigh : null;
    const avgPrice = parsePositive(row.avg_price);
    const rawVolume = parseNumber(row.volume_try);
    const volumeTry = rawVolume != null && rawVolume >= 0 ? rawVolume : null;

    rows.set(cleanDate, {
      ...row,
      date: cleanDate,
      close,
      low,
      high,
      avg_price: avgPrice,
      volume_try: volumeTry,
    });
  }
  return [...rows.values()].sort((a, b) => a.date.localeCompare(b.date));
}

export function movingAverage(values: number[], period: number): Array<number | null> {
  if (!Number.isInteger(period) || period < 1) throw new Error("Invalid period");
  let sum = 0;
  return values.map((value, index) => {
    sum += value;
    if (index >= period) sum -= values[index - period];
    return index >= period - 1 ? sum / period : null;
  });
}

// Wilder smoothing, seeded with the first period of price changes.
// https://www.tradingview.com/support/solutions/43000502338-relative-strength-index-rsi/
export function wilderRsi(values: number[], period = 14): Array<number | null> {
  if (!Number.isInteger(period) || period < 1) throw new Error("Invalid period");
  const output: Array<number | null> = Array(values.length).fill(null);
  let gain = 0, loss = 0;
  for (let i = 1; i < values.length; i++) {
    const change = values[i] - values[i - 1];
    const up = Math.max(change, 0), down = Math.max(-change, 0);
    if (i <= period) { gain += up / period; loss += down / period; }
    else { gain = (gain * (period - 1) + up) / period; loss = (loss * (period - 1) + down) / period; }
    // Completely flat data is shown as neutral, not as an overbought signal.
    if (i >= period) output[i] = gain === 0 && loss === 0 ? 50 : loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  }
  return output;
}

export function chartDomain(values: number[]): [number, number] {
  const finite = values.filter((v) => typeof v === "number" && Number.isFinite(v));
  if (!finite.length) return [0, 1];
  const min = finite.reduce((a, b) => Math.min(a, b));
  const max = finite.reduce((a, b) => Math.max(a, b));
  if (min === max) {
    const pad = Math.abs(min) * 0.05 || 1;
    return [min - pad, max + pad];
  }
  const pad = (max - min) * 0.08 || Math.abs(min) * 0.02 || 1;
  return [min - pad, max + pad];
}

// Missing observations start a new segment rather than being connected.
export function chartPath(
  values: Array<number | null | undefined>,
  x: (index: number) => number,
  y: (value: number) => number,
): string {
  let connected = false;
  return values
    .map((value, index) => {
      if (value == null || typeof value !== "number" || !Number.isFinite(value)) {
        connected = false;
        return "";
      }
      const px = x(index);
      const py = y(value);
      if (!Number.isFinite(px) || !Number.isFinite(py)) {
        connected = false;
        return "";
      }
      const command = connected ? "L" : "M";
      connected = true;
      return `${command}${px},${py}`;
    })
    .join(" ");
}

export function rangeStart(end: string, days: number) {
  const cleanEnd = extractChartDate(end) || end;
  const ts = Date.parse(`${cleanEnd}T00:00:00Z`);
  if (!Number.isFinite(ts)) return cleanEnd;
  return new Date(ts - days * 86400000).toISOString().slice(0, 10);
}

// Bir gostergeyi (orn. BIST100) baska bir serinin (orn. portfoy) tarihlerine
// hizalar ve ilk eslesen gunden itibaren yuzdesel degisim serisi uretir.
// Eslesmeyen tarihler icin en son mevcut gostergeye bakilir (haftasonu/tatil
// gibi portfoy gununun endeks gununden az kaydigi durumlarda kopuk olmasin).
export function benchmarkChangeSeries(
  dates: string[],
  benchmark: Array<{ date: string; value: number }>,
): Array<number | null> {
  if (!Array.isArray(benchmark)) return dates.map(() => null);
  const sorted = benchmark
    .map((row) => ({
      date: extractChartDate(row?.date),
      value: parsePositive(row?.value),
    }))
    .filter((row): row is { date: string; value: number } => row.date != null && row.value != null)
    .sort((a, b) => a.date.localeCompare(b.date));

  let cursor = 0, base: number | null = null;
  return dates.map((rawDate) => {
    const date = extractChartDate(rawDate) || rawDate;
    while (cursor < sorted.length && sorted[cursor].date <= date) cursor++;
    const latest = cursor > 0 ? sorted[cursor - 1].value : null;
    if (latest == null) return null;
    base ??= latest;
    return (latest / base - 1) * 100;
  });
}

export type ValuePoint = { date: string; value: number };

export function performanceSeries(source: ValuePoint[]) {
  if (!Array.isArray(source)) return [];
  const dates = new Map<string, ValuePoint>();
  for (const point of source) {
    if (!point) continue;
    const cleanDate = extractChartDate(point.date);
    const value = parseNumber(point.value);
    if (cleanDate && value != null && value >= 0) {
      dates.set(cleanDate, { date: cleanDate, value });
    }
  }
  const rows = [...dates.values()].sort((a, b) => a.date.localeCompare(b.date));
  let peak = 0;
  return rows.map((row) => {
    peak = Math.max(peak, row.value);
    return { ...row, drawdown: peak > 0 ? (row.value / peak - 1) * 100 : 0 };
  });
}
