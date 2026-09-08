import type { Price } from "./types";

export function validChartDate(value: string) {
  const timestamp = Date.parse(`${value}T00:00:00Z`);
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(timestamp) && new Date(timestamp).toISOString().slice(0, 10) === value;
}

export function normalizePrices(source: Price[]): Price[] {
  const rows = new Map<string, Price>();
  const positive = (value: number | null) => value != null && Number.isFinite(value) && value > 0 ? value : null;
  for (const row of source) {
    if (!validChartDate(row.date) || positive(row.close) == null) continue;
    const low = positive(row.low), high = positive(row.high);
    rows.set(row.date, { ...row, low: low != null && low <= row.close ? low : null, high: high != null && high >= row.close ? high : null,
      avg_price: positive(row.avg_price), volume_try: row.volume_try != null && Number.isFinite(row.volume_try) && row.volume_try >= 0 ? row.volume_try : null });
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
  const finite = values.filter(Number.isFinite);
  if (!finite.length) return [0, 1];
  const min = finite.reduce((a, b) => Math.min(a, b)), max = finite.reduce((a, b) => Math.max(a, b));
  const pad = (max - min) * .08 || Math.abs(min) * .02 || 1;
  return [min - pad, max + pad];
}

// Missing observations start a new segment rather than being connected.
export function chartPath(values: Array<number | null>, x: (index: number) => number, y: (value: number) => number) {
  let connected = false;
  return values.map((value, index) => {
    if (value == null || !Number.isFinite(value)) { connected = false; return ""; }
    const command = connected ? "L" : "M";
    connected = true;
    return `${command}${x(index)},${y(value)}`;
  }).join(" ");
}

export function rangeStart(end: string, days: number) {
  return new Date(Date.parse(`${end}T00:00:00Z`) - days * 86400000).toISOString().slice(0, 10);
}

// Bir gostergeyi (orn. BIST100) baska bir serinin (orn. portfoy) tarihlerine
// hizalar ve ilk eslesen gunden itibaren yuzdesel degisim serisi uretir.
// Eslesmeyen tarihler icin en son mevcut gostergeye bakilir (haftasonu/tatil
// gibi portfoy gununun endeks gununden az kaydigi durumlarda kopuk olmasin).
export function benchmarkChangeSeries(
  dates: string[],
  benchmark: Array<{ date: string; value: number }>,
): Array<number | null> {
  const sorted = [...benchmark]
    .filter((row) => validChartDate(row.date) && Number.isFinite(row.value) && row.value > 0)
    .sort((a, b) => a.date.localeCompare(b.date));
  let cursor = 0, base: number | null = null;
  return dates.map((date) => {
    while (cursor < sorted.length && sorted[cursor].date <= date) cursor++;
    const latest = cursor > 0 ? sorted[cursor - 1].value : null;
    if (latest == null) return null;
    base ??= latest;
    return (latest / base - 1) * 100;
  });
}

export type ValuePoint = { date: string; value: number };
export function performanceSeries(source: ValuePoint[]) {
  const dates = new Map<string, ValuePoint>();
  for (const point of source) if (validChartDate(point.date) && Number.isFinite(point.value) && point.value >= 0) dates.set(point.date, point);
  const rows = [...dates.values()].sort((a, b) => a.date.localeCompare(b.date));
  let peak = 0;
  return rows.map((row) => {
    peak = Math.max(peak, row.value);
    return { ...row, drawdown: peak > 0 ? (row.value / peak - 1) * 100 : 0 };
  });
}
