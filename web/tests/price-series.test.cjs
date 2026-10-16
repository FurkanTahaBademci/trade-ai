const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/price-series.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const { compactPrices, expandPrices } = loaded.exports;

test("compact price rows round-trip the fields the chart uses", () => {
  const rows = [{ date: "2026-10-15", close: 341.75, high: 345, low: 338.5, avg_price: 341.2, volume_try: 1234567, close_usd: 8.1, market_cap_try: 1.6e12 }];
  const compact = compactPrices(rows);
  assert.deepEqual(compact, [["2026-10-15", 341.75, 345, 338.5, 341.2, 1234567]]);
  assert.deepEqual(expandPrices(compact), [{ date: "2026-10-15", close: 341.75, high: 345, low: 338.5, avg_price: 341.2, volume_try: 1234567, close_usd: null, market_cap_try: null }]);
  assert.ok(JSON.stringify(compact).length < JSON.stringify(rows).length / 2);
});
