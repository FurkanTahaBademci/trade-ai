const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

function loadTs(relPath) {
  const file = path.resolve(__dirname, relPath);
  const code = readFileSync(file, "utf8");
  const compiled = ts.transpileModule(code, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });
  const m = new Module(file, module);
  m.require = function(request) {
    if (request.startsWith("./") || request.startsWith("../")) {
      const targetPath = path.resolve(path.dirname(file), request);
      const withTs = targetPath.endsWith(".ts") ? targetPath : targetPath + ".ts";
      return loadTs(path.relative(__dirname, withTs));
    }
    return Module.prototype.require.call(this, request);
  };
  m._compile(compiled.outputText, file);
  return m.exports;
}

const { prepareTradingViewData, getTradingViewThemeColors } = loadTs("../src/lib/tradingview-data.ts");

test("prepareTradingViewData returns empty bundle for empty prices", () => {
  const bundle = prepareTradingViewData([]);
  assert.equal(bundle.count, 0);
  assert.deepEqual(bundle.candles, []);
  assert.deepEqual(bundle.area, []);
  assert.deepEqual(bundle.volume, []);
});

test("prepareTradingViewData constructs valid candlesticks with clamped wicks and synthetic open", () => {
  const prices = [
    { date: "2026-01-01", close: 100, high: 105, low: 95, avg_price: 98, volume_try: 50000 },
    { date: "2026-01-02", close: 110, high: 108, low: 99, avg_price: 104, volume_try: 75000 }, // high is lower than close -> clamped
  ];
  const bundle = prepareTradingViewData(prices);
  assert.equal(bundle.count, 2);

  // First candle uses avg_price or close as initial open
  assert.equal(bundle.candles[0].time, "2026-01-01");
  assert.equal(bundle.candles[0].open, 98);
  assert.equal(bundle.candles[0].close, 100);
  assert.equal(bundle.candles[0].high, 105);
  assert.equal(bundle.candles[0].low, 95);

  // Second candle opens at prev close (100). High was 108 in data, but close is 110, so high is clamped to Math.max(108, 100, 110) = 110!
  assert.equal(bundle.candles[1].time, "2026-01-02");
  assert.equal(bundle.candles[1].open, 100);
  assert.equal(bundle.candles[1].close, 110);
  assert.equal(bundle.candles[1].high, 110);
  assert.equal(bundle.candles[1].low, 99);

  // Volume colors: first candle is up (100 >= 98) -> green, second candle is up (110 >= 100) -> green
  assert.ok(bundle.volume[0].color.includes("163, 74"));
  assert.ok(bundle.volume[1].color.includes("163, 74"));
});

test("prepareTradingViewData assigns red volume color on down days", () => {
  const prices = [
    { date: "2026-01-01", close: 100, high: 105, low: 95, avg_price: 100, volume_try: 50000 },
    { date: "2026-01-02", close: 90, high: 102, low: 88, avg_price: 95, volume_try: 60000 },
  ];
  const bundle = prepareTradingViewData(prices);
  assert.equal(bundle.candles[1].close < bundle.candles[1].open, true);
  assert.ok(bundle.volume[1].color.includes("239, 68, 68")); // red
});

test("getTradingViewThemeColors provides distinct dark and light palettes", () => {
  const dark = getTradingViewThemeColors(true);
  const light = getTradingViewThemeColors(false);

  assert.equal(dark.background, "#111922");
  assert.equal(light.background, "#ffffff");
  assert.notEqual(dark.textColor, light.textColor);
  assert.notEqual(dark.gridColor, light.gridColor);
  assert.notEqual(dark.lineColor, light.lineColor);
});
