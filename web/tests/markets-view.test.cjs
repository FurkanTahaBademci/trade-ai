const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/markets-view.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const { parseMarketsView, marketsViewQuery, nextSort, defaultOrder, DEFAULT_MARKETS_VIEW } = loaded.exports;

test("parseMarketsView falls back to the default list view for missing or junk params", () => {
  assert.deepEqual(parseMarketsView({}), DEFAULT_MARKETS_VIEW);
  assert.deepEqual(parseMarketsView({ view: "pie", sort: "drop table", order: "sideways" }), { view: "table", sort: "ticker", order: "asc" });
});

test("parseMarketsView reads view, sort and order; order defaults per column", () => {
  assert.deepEqual(parseMarketsView({ view: "heatmap" }), { view: "heatmap", sort: "ticker", order: "asc" });
  assert.deepEqual(parseMarketsView({ sort: "change" }), { view: "table", sort: "change", order: "desc" });
  assert.deepEqual(parseMarketsView({ sort: ["volume", "score"], order: "asc" }), { view: "table", sort: "volume", order: "asc" });
});

test("marketsViewQuery omits defaults and round-trips through parse", () => {
  assert.equal(marketsViewQuery(DEFAULT_MARKETS_VIEW), "");
  assert.equal(marketsViewQuery({ view: "table", sort: "change", order: "desc" }), "sort=change");
  assert.equal(marketsViewQuery({ view: "heatmap", sort: "ticker", order: "desc" }), "view=heatmap&order=desc");
  for (const state of [
    { view: "heatmap", sort: "score", order: "asc" },
    { view: "table", sort: "price", order: "desc" },
    { view: "table", sort: "ticker", order: "desc" },
  ]) {
    const query = Object.fromEntries(new URLSearchParams(marketsViewQuery(state)));
    assert.deepEqual(parseMarketsView(query), state);
  }
});

test("nextSort toggles direction on the active column and resets on a new one", () => {
  assert.deepEqual(nextSort({ sort: "change", order: "desc" }, "change"), { sort: "change", order: "asc" });
  assert.deepEqual(nextSort({ sort: "change", order: "asc" }, "change"), { sort: "change", order: "desc" });
  assert.deepEqual(nextSort({ sort: "change", order: "asc" }, "ticker"), { sort: "ticker", order: "asc" });
  assert.deepEqual(nextSort({ sort: "ticker", order: "asc" }, "volume"), { sort: "volume", order: "desc" });
  assert.equal(defaultOrder("score"), "desc");
});
