const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

function load(rel) {
  const file = path.resolve(__dirname, rel);
  const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });
  const loaded = new Module(file, module);
  loaded.filename = file;
  loaded.paths = module.paths;
  loaded._compile(compiled.outputText, file);
  return loaded.exports;
}

const chart = load("../src/lib/chart-data.ts");
const origResolve = Module._resolveFilename;
Module._resolveFilename = function (request, ...rest) {
  if (request === "./chart-data") return path.resolve(__dirname, "../src/lib/chart-data.ts");
  return origResolve.call(this, request, ...rest);
};
require.extensions[".ts"] = (mod, filename) => {
  mod._compile(ts.transpileModule(readFileSync(filename, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, filename);
};
const { normalizeHistory, scoreDelta, labelChanges, componentSeries, driverKindName } = load("../src/lib/signal-history.ts");
void chart;

const pt = (date, score, label = "NEUTRAL", components = {}) => ({ as_of_date: date, composite_score: score, signal_label: label, confidence: 0.5, component_scores: components });

test("normalizeHistory drops invalid rows, dedupes and sorts ascending", () => {
  const rows = normalizeHistory([pt("2026-09-03", 60), pt("bad", 10), pt("2026-09-01", "x"), pt("2026-09-02", 55), pt("2026-09-03", 62)]);
  assert.deepEqual(rows.map((r) => [r.as_of_date, r.composite_score]), [["2026-09-02", 55], ["2026-09-03", 62]]);
  assert.deepEqual(normalizeHistory(null), []);
});

test("scoreDelta compares against the nearest point at or before the horizon", () => {
  const rows = [pt("2026-08-01", 40), pt("2026-08-25", 50), pt("2026-09-01", 55), pt("2026-09-02", 58)];
  assert.equal(scoreDelta(rows, 1), 3);
  assert.equal(scoreDelta(rows, 7), 8);
  assert.equal(scoreDelta(rows, 30), 18);
  assert.equal(scoreDelta(rows, 90), null);
  assert.equal(scoreDelta([pt("2026-09-01", 50)], 1), null);
});

test("labelChanges marks only the points where the label flips", () => {
  const rows = [pt("2026-09-01", 50, "NEUTRAL"), pt("2026-09-02", 61, "POSITIVE"), pt("2026-09-03", 63, "POSITIVE"), pt("2026-09-04", 45, "NEUTRAL")];
  assert.deepEqual(labelChanges(rows).map((c) => [c.date, c.from, c.to, c.index]), [["2026-09-02", "NEUTRAL", "POSITIVE", 1], ["2026-09-04", "POSITIVE", "NEUTRAL", 3]]);
  assert.deepEqual(labelChanges([]), []);
});

test("componentSeries leaves gaps for missing components", () => {
  const rows = [pt("2026-09-01", 50, "NEUTRAL", { llm: 60 }), pt("2026-09-02", 50, "NEUTRAL", {})];
  assert.deepEqual(componentSeries(rows, "llm"), [60, null]);
  assert.equal(driverKindName("kap"), "KAP");
  assert.equal(driverKindName("x"), "x");
});
