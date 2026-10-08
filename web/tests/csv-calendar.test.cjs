const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

function load(name) {
  const file = path.resolve(__dirname, `../src/lib/${name}.ts`);
  const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });
  const loaded = new Module(file, module);
  loaded._compile(compiled.outputText, file);
  return loaded.exports;
}
const { sanitizeCell, buildCsv, CSV_BOM } = load("csv");
const { parseMonth, shiftMonth, monthRange, groupByDate, parseTypes } = load("calendar");

test("sanitizeCell neutralizes formula prefixes", () => {
  for (const value of ["=1+1", "+SUM(A1)", "-2+3", "@cmd", "\t=x", "  =x"]) assert.equal(sanitizeCell(value)[0], "'");
  assert.equal(sanitizeCell("THYAO"), "THYAO");
  assert.equal(sanitizeCell("a=b"), "a=b");
});

test("buildCsv uses BOM, semicolons, quoting and decimal comma", () => {
  const csv = buildCsv(["Hisse", "Not"], [["THYAO", '=HYPERLINK("x";"y")'], ["A;B", -1.5], ["C", null]]);
  assert.ok(csv.startsWith(CSV_BOM));
  const lines = csv.slice(1).split("\r\n");
  assert.equal(lines[0], "Hisse;Not");
  assert.equal(lines[1], `THYAO;"'=HYPERLINK(""x"";""y"")"`);
  assert.equal(lines[2], '"A;B";-1,5');
  assert.equal(lines[3], "C;");
});

test("month helpers", () => {
  assert.equal(parseMonth("2026-13", "2026-10"), "2026-10");
  assert.equal(parseMonth("2026-02", "2026-10"), "2026-02");
  assert.equal(shiftMonth("2026-12", 1), "2027-01");
  assert.equal(shiftMonth("2026-01", -1), "2025-12");
  assert.deepEqual(monthRange("2028-02"), { start: "2028-02-01", end: "2028-02-29" });
});

test("groupByDate and parseTypes", () => {
  const groups = groupByDate([{ date: "2026-10-05", id: "b" }, { date: "2026-10-01", id: "a" }, { date: "2026-10-05", id: "c" }]);
  assert.deepEqual(groups.map(([d, e]) => [d, e.length]), [["2026-10-01", 1], ["2026-10-05", 2]]);
  assert.deepEqual(parseTypes("DIVIDEND,bogus,PPK,DIVIDEND"), ["DIVIDEND", "PPK"]);
  assert.deepEqual(parseTypes(undefined), []);
});
