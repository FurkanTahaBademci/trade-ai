const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/chart-data.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const { movingAverage, wilderRsi, bollingerBands, chartDomain, chartPath, normalizePrices, rangeStart, performanceSeries, validChartDate, benchmarkChangeSeries } = loaded.exports;
const price = (date, close, extra = {}) => ({ date, close, low: null, high: null, avg_price: null, volume_try: null, close_usd: null, market_cap_try: null, ...extra });
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-8, `${actual} != ${expected}`);

test("moving averages warm up on full history before the visible range is sliced", () => {
  const values = Array.from({ length: 80 }, (_, i) => i + 1);
  const ma = movingAverage(values, 50);
  assert.equal(ma[48], null);
  near(ma[49], 25.5);
  near(ma.slice(60)[0], 36.5);
  assert.deepEqual(movingAverage([], 20), []);
  assert.throws(() => movingAverage(values, 0));
});

test("bollinger bands compute upper, middle, and lower bands correctly", () => {
  const values = Array(30).fill(100);
  const bbFlat = bollingerBands(values, 20, 2);
  assert.equal(bbFlat.middle[18], null);
  assert.equal(bbFlat.middle[19], 100);
  // Zero standard deviation means upper === middle === lower
  assert.equal(bbFlat.upper[19], 100);
  assert.equal(bbFlat.lower[19], 100);

  // Dynamic values
  const dynamic = Array.from({ length: 25 }, (_, i) => 10 + i * 2);
  const bbDyn = bollingerBands(dynamic, 20, 2);
  assert.ok(bbDyn.upper[19] > bbDyn.middle[19]);
  assert.ok(bbDyn.lower[19] < bbDyn.middle[19]);
  near(bbDyn.upper[19] - bbDyn.middle[19], bbDyn.middle[19] - bbDyn.lower[19]);
});

test("RSI uses a Wilder recurrence after the seed, not a rolling simple average", () => {
  const values = [1, 2, 3, 2, 4, 3];
  const result = wilderRsi(values, 3);
  assert.deepEqual(result.slice(0, 3), [null, null, null]);
  near(result[3], 100 - 100 / 3);
  near(result[4], 100 - 100 / 6);
  near(result[5], 100 - 100 / (1 + 20 / 13));
});

test("RSI handles rising, falling, flat and insufficient history explicitly", () => {
  near(wilderRsi(Array.from({ length: 20 }, (_, i) => i + 1)).at(-1), 100);
  near(wilderRsi(Array.from({ length: 20 }, (_, i) => 20 - i)).at(-1), 0);
  near(wilderRsi(Array(20).fill(10)).at(-1), 50);
  assert.deepEqual(wilderRsi([10, 12]), [null, null]);
  assert.throws(() => wilderRsi([10], 1.5));
});

test("price data is sorted, deduplicated and invalid values never reach the SVG", () => {
  const result = normalizePrices([
    price("2026-01-03", 100, { low: 110, high: 90, volume_try: -5, avg_price: NaN }),
    price("2026-01-01", 10), price("2026-01-01", 12),
    price("2026-01-02", 30, { low: 20, volume_try: 0 }),
    price("2026-02-30", 10), price("2026-01-04", NaN), price("2026-01-05", 0),
  ]);
  assert.deepEqual(result.map((row) => row.close), [12, 30, 100]);
  assert.equal(result[1].low, 20); assert.equal(result[1].high, null);
  assert.equal(result[1].volume_try, 0);
  for (const key of ["low", "high", "volume_try", "avg_price"]) assert.equal(result[2][key], null);
});

test("empty and flat chart domains stay finite and center the series", () => {
  assert.deepEqual(chartDomain([NaN, Infinity]), [0, 1]);
  const [min, max] = chartDomain([100, 100]);
  assert.ok(min < 100 && max > 100);
  near((100 - min) / (max - min), .5);
  assert.deepEqual(chartDomain([0]), [-1, 1]);
});

test("missing chart samples break paths rather than inventing connecting values", () => {
  assert.equal(chartPath([null, 10, 20, null, 30, NaN, 40], (i) => i, (v) => v).trim(), "M1,10 L2,20  M4,30  M6,40");
});

test("date ranges use UTC calendar dates and handle leap years", () => {
  assert.equal(rangeStart("2024-03-01", 1), "2024-02-29");
  assert.equal(rangeStart("2026-01-01", 30), "2025-12-02");
  assert.equal(validChartDate("2025-02-29"), false);
  assert.equal(validChartDate("2024-02-29"), true);
});

test("drawdown retains the historical peak when the displayed period is narrowed", () => {
  const rows = performanceSeries([
    { date: "2026-01-03", value: 90 }, { date: "2026-01-01", value: 100 },
    { date: "2026-01-02", value: 120 }, { date: "2026-01-04", value: 126 },
  ]);
  assert.deepEqual(rows.map((row) => row.drawdown), [0, 0, -25, 0]);
  assert.equal(rows.slice(2)[0].drawdown, -25);
  assert.deepEqual(performanceSeries([{ date: "bad", value: 100 }, { date: "2026-01-01", value: -1 }]), []);
});

test("benchmarkChangeSeries bases the percentage on the first matched trading day", () => {
  const benchmark = [
    { date: "2026-01-01", value: 100 }, { date: "2026-01-02", value: 110 }, { date: "2026-01-05", value: 121 },
  ];
  const result = benchmarkChangeSeries(["2026-01-01", "2026-01-02", "2026-01-05"], benchmark);
  result.forEach((value, i) => near(value, [0, 10, 21][i]));
});

test("benchmarkChangeSeries carries the last known value across a gap (e.g. weekend)", () => {
  const benchmark = [{ date: "2026-01-01", value: 100 }, { date: "2026-01-05", value: 105 }];
  const result = benchmarkChangeSeries(["2026-01-01", "2026-01-03", "2026-01-05"], benchmark);
  result.forEach((value, i) => near(value, [0, 0, 5][i]));
});

test("benchmarkChangeSeries returns null before any benchmark data exists and ignores invalid rows", () => {
  const benchmark = [{ date: "bad-date", value: 50 }, { date: "2026-01-03", value: -5 }, { date: "2026-01-05", value: 200 }];
  const result = benchmarkChangeSeries(["2026-01-01", "2026-01-03", "2026-01-05"], benchmark);
  assert.deepEqual(result, [null, null, 0]);
});

test("handles ISO timestamps and Date objects seamlessly across charts", () => {
  assert.equal(validChartDate("2026-09-08T00:00:00"), true);
  assert.equal(validChartDate("2026-09-08T15:30:00Z"), true);
  assert.equal(validChartDate(new Date("2026-09-08T00:00:00Z")), true);
  const normalized = normalizePrices([
    { date: "2026-09-08T00:00:00Z", close: "150.5" },
    { date: "2026-09-09T10:00:00", close: 152 },
  ]);
  assert.deepEqual(normalized.map((r) => r.date), ["2026-09-08", "2026-09-09"]);
  assert.equal(normalized[0].close, 150.5);

  const perf = performanceSeries([
    { date: "2026-09-08T00:00:00", value: 1000000 },
    { date: "2026-09-09T00:00:00", value: 1050000 },
  ]);
  assert.equal(perf.length, 2);
  assert.equal(perf[0].date, "2026-09-08");
});
