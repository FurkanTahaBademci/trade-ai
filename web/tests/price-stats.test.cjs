const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/price-stats.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const { priceStats } = loaded.exports;

const row = (date, close, low = null, high = null) => ({ date, close, low, high, avg_price: null, volume_try: null, close_usd: null, market_cap_try: null });

test("priceStats ignores prices older than 52 weeks and prefers intraday low/high", () => {
  const stats = priceStats([row("2025-01-02", 5), row("2025-11-01", 80, 75, 90), row("2026-10-13", 100, 95, 120), row("2026-10-14", 110, 100, 112)]);
  assert.equal(stats.low52, 75);
  assert.equal(stats.high52, 120);
  assert.equal(Math.round(stats.dayChange), 10);
  assert.equal(Math.round(stats.position52), 78);
});

test("priceStats handles empty and single-row history", () => {
  assert.deepEqual(priceStats([]), { dayChange: null, low52: null, high52: null, position52: null });
  const single = priceStats([row("2026-10-14", 50)]);
  assert.equal(single.dayChange, null);
  assert.equal(single.low52, 50);
  assert.equal(single.position52, null);
});
