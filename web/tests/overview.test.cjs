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

const overview = load("../src/lib/overview.ts");

test("index snapshot uses the last two valid closes regardless of input order", () => {
  const snap = overview.indexSnapshot([
    { date: "2026-10-16", value: 10200 },
    { date: "2026-10-14", value: 9900 },
    { date: "2026-10-15", value: 10000 },
    { date: "2026-10-17", value: 0 },
  ]);
  assert.equal(snap.value, 10200);
  assert.equal(snap.date, "2026-10-16");
  assert.ok(Math.abs(snap.changePct - 2) < 1e-9);
  assert.equal(overview.indexSnapshot([]), null);
  assert.equal(overview.indexSnapshot([{ date: "2026-10-16", value: 10 }]).changePct, null);
});

function stock(ticker, change_pct, volume_try = 50_000_000) {
  return { ticker, name: ticker, last_price: 10, change_pct, volume_try };
}

test("movers rank by daily change and skip illiquid names when enough liquid ones exist", () => {
  const stocks = [
    stock("TAVAN", 10, 100_000),
    ...["A", "B", "C", "D", "E", "F"].map((t, i) => stock(t, i + 1)),
    ...["K", "L", "M", "N", "O", "P"].map((t, i) => stock(t, -(i + 1))),
    stock("FLAT", 0),
  ];
  const { gainers, losers } = overview.marketMovers(stocks, 5);
  assert.deepEqual(gainers.map((s) => s.ticker), ["F", "E", "D", "C", "B"]);
  assert.deepEqual(losers.map((s) => s.ticker), ["P", "O", "N", "M", "L"]);
});

test("movers fall back to all priced stocks when liquidity data is thin", () => {
  const stocks = [stock("X", 5, 0), stock("Y", -3, 0), { ...stock("Z", 9), last_price: 0 }];
  const { gainers, losers } = overview.marketMovers(stocks, 5);
  assert.deepEqual(gainers.map((s) => s.ticker), ["X"]);
  assert.deepEqual(losers.map((s) => s.ticker), ["Y"]);
});

test("signal distribution groups labels and treats empty data as missing", () => {
  assert.deepEqual(
    overview.signalDistribution({ VERY_POSITIVE: 3, POSITIVE: 10, NEUTRAL: 500, NEGATIVE: 20, VERY_NEGATIVE: 2 }),
    { positive: 13, neutral: 500, negative: 22, total: 535 },
  );
  assert.equal(overview.signalDistribution({}), null);
  assert.equal(overview.signalDistribution(null), null);
});

test("briefing mood label says insufficient data only when no confident score exists", () => {
  assert.equal(overview.moodLabel("NEUTRAL", 0), "Yetersiz veri");
  assert.equal(overview.moodLabel("NEUTRAL", undefined), "Yetersiz veri");
  assert.equal(overview.moodLabel("NEUTRAL", 120), "Nötr skor görünümü");
  assert.equal(overview.moodLabel("BULLISH", 0), "Pozitif skor görünümü");
  assert.equal(overview.moodLabel("BEARISH", 5), "Negatif skor görünümü");
});

test("home page no longer promotes the first evaluation regardless of impact", () => {
  const page = readFileSync(path.resolve(__dirname, "../src/app/page.tsx"), "utf8");
  assert.ok(!page.includes("evaluations.data.find"));
  assert.ok(page.includes("/api/ai/focus"));
  assert.ok(!page.includes('label="Takip evreni"'));
  assert.ok(!page.includes('label="Haber havuzu"'));
});
