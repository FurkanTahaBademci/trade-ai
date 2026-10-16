const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

// Use the installed TypeScript compiler; no additional test dependency needed.
const file = path.resolve(__dirname, "../src/lib/backtest-form.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const { backtestFields, validateBacktestForm, componentWeights } = loaded.exports;
const values = () => ({
  ...Object.fromEntries(Object.entries(backtestFields).map(([name, field]) => [name, field.value])),
  start_date: "2025-09-08", end_date: "2026-09-08",
});

test("default configuration and a valid leap day are accepted", () => {
  assert.deepEqual(validateBacktestForm(values()), {});
  assert.deepEqual(validateBacktestForm({ ...values(), start_date: "2024-02-29" }), {});
});
test("reject invalid dates, reversed periods and excessive history", () => {
  assert.ok(validateBacktestForm({ ...values(), start_date: "2025-02-29" }).start_date);
  assert.ok(validateBacktestForm({ ...values(), end_date: "2024-01-01" }).end_date);
  assert.ok(validateBacktestForm({ ...values(), start_date: "2000-01-01" }).end_date);
});
test("cross-field rules prevent inverted scores and over-allocation", () => {
  assert.ok(validateBacktestForm({ ...values(), exit_score: "80" }).exit_score);
  assert.ok(validateBacktestForm({ ...values(), max_positions: "11" }).max_position_weight);
});
test("reject missing, nonfinite and fractional share-slot values", () => {
  for (const initial_cash of ["", "Infinity", "NaN", "-1"]) {
    assert.ok(validateBacktestForm({ ...values(), initial_cash }).initial_cash);
  }
  assert.ok(validateBacktestForm({ ...values(), max_positions: "2.5" }).max_positions);
});

test("basket and weight fields have safe defaults and cross-field rules", () => {
  assert.equal(values().strategy, "threshold");
  assert.equal(values().exit_score, "55");
  assert.ok(validateBacktestForm({ ...values(), strategy: "momentum" }).strategy);
  assert.deepEqual(validateBacktestForm({ ...values(), strategy: "basket" }), {});
  assert.ok(validateBacktestForm({ ...values(), basket_size: "30", basket_keep: "20" }).basket_keep);
  const zero = { weight_llm: "0", weight_fundamental: "0", weight_analyst: "0", weight_momentum: "0" };
  assert.ok(validateBacktestForm({ ...values(), ...zero }).weight_llm);
});
test("live weights send no override; changed weights are sent as fractions", () => {
  assert.equal(componentWeights(values()), null);
  assert.deepEqual(componentWeights({ ...values(), weight_analyst: "0", weight_llm: "45" }), {
    llm: 0.45, fundamental: 0.28, analyst: 0, momentum: 0.15,
  });
});
