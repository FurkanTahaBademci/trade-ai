const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

function load(relative) {
  const file = path.resolve(__dirname, relative);
  const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
  });
  const loaded = new Module(file, module);
  loaded._compile(compiled.outputText, file);
  return loaded.exports;
}

const { STRATEGY_FIELDS, parseStrategyConfig, parseAmount } = load("../src/lib/paper-forms.ts");

const MODEL = { entry_score: 75, exit_score: 55, min_confidence: 0.25, min_coverage: 2, max_positions: 10, max_new_entries_per_day: 3, max_position_weight_pct: 10, max_sector_weight_pct: 30, stop_loss_pct: 15, take_profit_pct: 0, trailing_stop_pct: 0 };

function form(values) {
  return (name) => values[name];
}

function fields(overrides = {}) {
  const values = { cfg_rebalance_enabled: "on" };
  for (const [key, value] of Object.entries({ ...MODEL, ...overrides })) values[`cfg_${key}`] = String(value);
  return values;
}

test("strategy form parses the model defaults including the checkbox", () => {
  const result = parseStrategyConfig(form(fields()));
  assert.deepEqual(result, { config: { ...MODEL, rebalance_enabled: true } });
  const off = parseStrategyConfig(form({ ...fields(), cfg_rebalance_enabled: undefined }));
  assert.equal(off.config.rebalance_enabled, false);
  assert.equal(STRATEGY_FIELDS.length, Object.keys(MODEL).length);
});

test("strategy form rejects out-of-range values and inconsistent thresholds", () => {
  assert.match(parseStrategyConfig(form(fields({ entry_score: 40 }))).error, /Giriş skoru/);
  assert.match(parseStrategyConfig(form(fields({ entry_score: 60, exit_score: 70 }))).error, /Çıkış skoru/);
  assert.match(parseStrategyConfig(form(fields({ max_positions: 20, max_position_weight_pct: 10 }))).error, /%100/);
  assert.match(parseStrategyConfig(form({ ...fields(), cfg_stop_loss_pct: "" })).error, /Zarar-kes/);
  assert.equal(parseStrategyConfig(form(fields({ min_confidence: "0,4" }))).config.min_confidence, 0.4);
});

test("order sizes accept Turkish thousand separators and decimal commas", () => {
  assert.equal(parseAmount("10.000"), 10000);
  assert.equal(parseAmount("1.000.000"), 1000000);
  assert.equal(parseAmount("2.500,75"), 2500.75);
  assert.equal(parseAmount("150"), 150);
  assert.equal(parseAmount("12.5"), 12.5);
  assert.equal(parseAmount(""), null);
  assert.equal(parseAmount("-5"), null);
  assert.equal(parseAmount("abc"), null);
});
