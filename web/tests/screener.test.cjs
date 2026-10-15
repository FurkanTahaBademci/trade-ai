const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/screener.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const { parseDecimal, parseScreenerParams, screenerApiQuery, screenerHref, sortHref, activeFilterCount, moreHref, screenerLimit } = loaded.exports;

test("parseDecimal accepts Turkish decimals and rejects junk", () => {
  assert.equal(parseDecimal("10,5"), 10.5);
  assert.equal(parseDecimal(" 1 000 "), 1000);
  assert.equal(parseDecimal("abc"), null);
  assert.equal(parseDecimal(""), null);
});

test("parseScreenerParams keeps only known, valid values", () => {
  const params = parseScreenerParams({ q: " thy ", sort: "drop table", order: "sideways", signal: "BUY", max_pe: "12,5", min_roe: "x", sector: "Banka" });
  assert.deepEqual(params, { sort: "composite_score", order: "desc", q: "thy", sector: "Banka", max_pe: "12,5" });
  assert.equal(activeFilterCount(params), 3);
});

test("screenerApiQuery maps signal groups to repeated labels and normalises numbers", () => {
  const query = new URLSearchParams(screenerApiQuery(parseScreenerParams({ signal: "pozitif", max_pe: "12,5", sort: "pe_ratio", order: "asc" }), 50));
  assert.deepEqual(query.getAll("label"), ["VERY_POSITIVE", "POSITIVE"]);
  assert.equal(query.get("max_pe"), "12.5");
  assert.equal(query.get("sort"), "pe_ratio");
  assert.equal(query.get("order"), "asc");
  assert.equal(query.get("limit"), "50");
  assert.equal(new URLSearchParams(screenerApiQuery(parseScreenerParams({}))).get("limit"), "100");
});

test("screenerHref omits defaults so the plain page URL stays clean", () => {
  assert.equal(screenerHref({ sort: "composite_score", order: "desc" }), "/tarayici");
  assert.equal(screenerHref({ sort: "pe_ratio", order: "asc", max_pe: "10" }), "/tarayici?sort=pe_ratio&order=asc&max_pe=10");
});

test("sortHref toggles the active column and starts valuation columns ascending", () => {
  const base = parseScreenerParams({});
  assert.equal(sortHref(base, "composite_score"), "/tarayici?order=asc");
  assert.equal(sortHref(base, "pe_ratio"), "/tarayici?sort=pe_ratio&order=asc");
  assert.equal(sortHref(base, "upside_pct"), "/tarayici?sort=upside_pct");
  assert.equal(sortHref(parseScreenerParams({ sort: "pe_ratio", order: "asc" }), "pe_ratio"), "/tarayici?sort=pe_ratio");
});

test("paging grows in 100-row steps up to 1000 and resets when sorting", () => {
  assert.equal(screenerLimit({}), 100);
  assert.equal(screenerLimit({ limit: "250" }), 300);
  assert.equal(screenerLimit({ limit: "99999" }), 1000);
  assert.equal(screenerLimit({ limit: "abc" }), 100);
  const params = parseScreenerParams({ max_pe: "10" });
  assert.equal(moreHref(params, 80), null);
  assert.equal(moreHref(params, 630), "/tarayici?max_pe=10&limit=200");
  const paged = parseScreenerParams({ limit: "200" });
  assert.equal(new URLSearchParams(screenerApiQuery(paged)).get("limit"), "200");
  assert.equal(sortHref(paged, "pe_ratio"), "/tarayici?sort=pe_ratio&order=asc");
  assert.equal(moreHref(parseScreenerParams({ limit: "1000" }), 5000), null);
});
