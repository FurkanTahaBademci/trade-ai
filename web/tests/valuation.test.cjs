const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/valuation.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const { valuationMultiples } = loaded.exports;

test("valuationMultiples uses trailing net income and equity", () => {
  const result = valuationMultiples(1_000, { ttm_net_income: 100, ttm_basis: "ttm", equity: 500 });
  assert.equal(result.pe, 10);
  assert.equal(result.pb, 2);
  assert.equal(result.basis, "son 12 ay kârı");
});

test("valuationMultiples hides multiples for losses, missing data and missing market cap", () => {
  assert.deepEqual(valuationMultiples(1_000, undefined), { pe: null, pb: null, basis: null });
  const loss = valuationMultiples(1_000, { ttm_net_income: -5, ttm_basis: "annual", equity: -1 });
  assert.equal(loss.pe, null);
  assert.equal(loss.pb, null);
  assert.equal(valuationMultiples(null, { ttm_net_income: 100, equity: 100 }).pe, null);
});
