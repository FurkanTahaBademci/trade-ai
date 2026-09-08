const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

function loadTypeScript(relativePath) {
  const file = path.resolve(__dirname, relativePath);
  const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });
  const loaded = new Module(file, module);
  loaded._compile(compiled.outputText, file);
  return loaded.exports;
}

const { normalizeMarketFeed, searchMarketFeed } = loadTypeScript("../src/lib/market-feed.ts");
const { normalizeWatchlist } = loadTypeScript("../src/lib/watchlist-data.ts");

test("watchlist values are normalized, deduplicated and constrained to ticker syntax", () => {
  assert.deepEqual(
    normalizeWatchlist([" thyao ", "THYAO", "asels", "", null, "../../bad", "A".repeat(17)]),
    ["THYAO", "ASELS"],
  );
  assert.deepEqual(normalizeWatchlist({ ticker: "THYAO" }), []);
});

test("market feed normalization rejects malformed rows and keeps the latest duplicate", () => {
  assert.deepEqual(normalizeMarketFeed([
    { ticker: " thyao ", name: " Türk Hava Yolları ", composite_score: 75.5, signal_label: "POSITIVE" },
    { ticker: "THYAO", name: "THY", composite_score: Infinity, signal_label: 4 },
    { ticker: "../bad", name: "Geçersiz" },
    { ticker: "ASELS", name: "" },
    null,
  ]), [{ ticker: "THYAO", name: "THY", composite_score: null, signal_label: null }]);
  assert.deepEqual(normalizeMarketFeed({}), []);
});

test("market search ranks exact and prefix ticker matches without mutating input", () => {
  const items = [
    { ticker: "THYAO", name: "Türk Hava Yolları", composite_score: null, signal_label: null },
    { ticker: "TAVHL", name: "TAV Havalimanları", composite_score: null, signal_label: null },
    { ticker: "THY", name: "Örnek", composite_score: null, signal_label: null },
  ];
  const original = [...items];
  assert.deepEqual(searchMarketFeed(items, "thy").map((item) => item.ticker), ["THY", "THYAO"]);
  assert.deepEqual(searchMarketFeed(items, "hava").map((item) => item.ticker), ["TAVHL", "THYAO"]);
  assert.deepEqual(searchMarketFeed(items, "", 2).map((item) => item.ticker), ["TAVHL", "THY"]);
  assert.deepEqual(searchMarketFeed(items, "thy", 0), []);
  assert.deepEqual(items, original);
});
