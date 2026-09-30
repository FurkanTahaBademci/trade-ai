const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/system-metrics.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const { signalCoverage } = loaded.exports;

test("signal coverage reports covered, missing and a one-decimal percentage", () => {
  assert.deepEqual(signalCoverage(809, 500), {
    total: 809,
    covered: 500,
    uncovered: 309,
    percentage: 61.8,
  });
});

test("signal coverage clamps invalid and inconsistent counters", () => {
  assert.deepEqual(signalCoverage(0, 12), { total: 0, covered: 0, uncovered: 0, percentage: 0 });
  assert.deepEqual(signalCoverage(10, 20), { total: 10, covered: 10, uncovered: 0, percentage: 100 });
  assert.deepEqual(signalCoverage(10, -4), { total: 10, covered: 0, uncovered: 10, percentage: 0 });
});
