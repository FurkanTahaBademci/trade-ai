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

test("formatMoney falls back to em dash and switches compact notation", () => {
  const standard = new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const compact = new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    notation: "compact",
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
  });

  assert.equal(formatMoney(null), "—");
  assert.equal(formatMoney(1234.5), standard.format(1234.5));
  assert.equal(formatMoney(1_500_000, true), compact.format(1_500_000));
});

test("formatPercent falls back to em dash and prefixes only positive signed values", () => {
  assert.equal(formatPercent(null), "—");
  assert.equal(formatPercent(5.2), "5,2%");
  assert.equal(formatPercent(5.2, true), "+5,2%");
  assert.equal(formatPercent(-5.2, true), "-5,2%");
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
