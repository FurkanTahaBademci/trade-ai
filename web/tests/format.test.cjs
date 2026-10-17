const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/format.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const {
  formatDate,
  relativeTime,
  formatNumber,
  formatMoney,
  formatPercent,
  formatBytes,
  sourceName,
  eventName,
  signalName,
  componentName,
} = loaded.exports;

test("formatDate falls back to em dash for missing or invalid input", () => {
  assert.equal(formatDate(""), "—");
  assert.equal(formatDate("not-a-date"), "—");
});

test("formatDate renders a valid ISO date without throwing", () => {
  const result = formatDate("2026-03-05T10:00:00Z");
  assert.notEqual(result, "—");
  assert.match(result, /2026/);
});

test("relativeTime falls back to em dash for missing or invalid input", () => {
  assert.equal(relativeTime(""), "—");
  assert.equal(relativeTime("not-a-date"), "—");
});

test("relativeTime buckets by minute/hour/day thresholds like the source formatter", () => {
  const formatter = new Intl.RelativeTimeFormat("tr", { numeric: "auto" });

  const fiveMinutesAgo = new Date(Date.now() - 5 * 60_000).toISOString();
  assert.equal(relativeTime(fiveMinutesAgo), formatter.format(-5, "minute"));

  const twoHoursAgo = new Date(Date.now() - 2 * 3_600_000).toISOString();
  assert.equal(relativeTime(twoHoursAgo), formatter.format(-2, "hour"));

  const threeDaysAgo = new Date(Date.now() - 3 * 86_400_000).toISOString();
  assert.equal(relativeTime(threeDaysAgo), formatter.format(-3, "day"));
});

test("formatNumber falls back to em dash for null/undefined/non-finite", () => {
  assert.equal(formatNumber(null), "—");
  assert.equal(formatNumber(undefined), "—");
  assert.equal(formatNumber(Number.NaN), "—");
  assert.equal(formatNumber(Number.POSITIVE_INFINITY), "—");
});

test("formatNumber respects the digits option and tr-TR grouping", () => {
  assert.equal(formatNumber(1234.567, 2), "1.234,57");
  assert.equal(formatNumber(1234.567, 0), "1.235");
});

test("formatMoney falls back to em dash and keeps two decimals in standard mode", () => {
  const standard = new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  assert.equal(formatMoney(null), "—");
  assert.equal(formatMoney(Number.NaN, true), "—");
  assert.equal(formatMoney(1234.5), standard.format(1234.5));
});

test("compact formatMoney uses a fixed single decimal and spells out Bin", () => {
  // Intl, kısaltmadan önce bölünmez boşluk koyar; karşılaştırma için normalleştir.
  const compact = (value) => formatMoney(value, true).replace(/\s/g, " ");
  assert.equal(compact(1_500_000), "₺1,5 Mn");
  assert.equal(compact(7.94e12), "₺7,9 Tn");
  assert.equal(compact(8e12), "₺8,0 Tn");
  assert.equal(compact(7.9e9), "₺7,9 Mr");
  assert.equal(compact(5_000), "₺5,0 Bin");
  assert.equal(compact(-3e6), "-₺3,0 Mn");
  assert.equal(compact(950), "₺950");
  assert.doesNotMatch(compact(12_000), / B$/);
});

test("formatPercent uses the Turkish prefix and a fixed number of decimals", () => {
  assert.equal(formatPercent(null), "—");
  assert.equal(formatPercent(undefined, true), "—");
  assert.equal(formatPercent(41.5), "%41,5");
  assert.equal(formatPercent(37), "%37,0");
  assert.equal(formatPercent(5.2, true), "+%5,2");
  assert.equal(formatPercent(-3, true), "-%3,0");
  assert.equal(formatPercent(-6.54), "-%6,5");
  assert.equal(formatPercent(1234.56), "%1.234,6");
  assert.equal(formatPercent(37, false, 0), "%37");
});

test("formatPercent never prints a sign for values that round to zero", () => {
  assert.equal(formatPercent(0, true), "%0,0");
  assert.equal(formatPercent(-0.04, true), "%0,0");
  assert.equal(formatPercent(0.04, true), "%0,0");
});

test("formatBytes falls back to em dash and picks the right unit", () => {
  assert.equal(formatBytes(null), "—");
  assert.equal(formatBytes(-1), "—");
  assert.equal(formatBytes(0), "0 B");
  assert.equal(formatBytes(512), "512 B");
  assert.equal(formatBytes(1536), "1,5 KB");
  assert.equal(formatBytes(1024 ** 2 * 3.2), "3,2 MB");
  assert.equal(formatBytes(1024 ** 3 * 1.1), "1,1 GB");
});

test("lookup helpers translate known keys and pass through unknown ones", () => {
  assert.equal(sourceName("foreks"), "Foreks");
  assert.equal(sourceName("unknown_source"), "unknown_source");
  assert.equal(eventName("earnings"), "Finansal sonuç");
  assert.equal(eventName(null), "Genel");
  assert.equal(signalName("VERY_POSITIVE"), "Çok pozitif");
  assert.equal(signalName("unknown"), "unknown");
  assert.equal(componentName("fund_flow"), "Fon akımı");
  assert.equal(componentName("unknown"), "unknown");
});

// Server and browser may use different host time zones. Both render Istanbul time.
test("formatDate uses Istanbul even when the host time zone changes", () => {
  const previous = process.env.TZ;
  try {
    process.env.TZ = "UTC";
    const utc = formatDate("2026-09-28T22:15:00Z", true);
    process.env.TZ = "America/Los_Angeles";
    assert.equal(formatDate("2026-09-28T22:15:00Z", true), utc);
    assert.match(utc, /29 Eyl/);
    assert.match(utc, /01:15/);
  } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
});
