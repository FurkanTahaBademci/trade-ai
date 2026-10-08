const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");

test("list-feed route defines all required feed kinds including watchlist and portfolio", () => {
  const routePath = path.resolve(__dirname, "../src/app/api/list-feed/[kind]/route.ts");
  const content = readFileSync(routePath, "utf8");

  // Verify route kinds exist
  assert.ok(content.includes("watchlist:"), "watchlist feed kind should be defined");
  assert.ok(content.includes("portfolio:"), "portfolio feed kind should be defined");
  assert.ok(content.includes("backtests:"), "backtests feed kind should be defined");
  assert.ok(content.includes("kap:"), "kap feed kind should be defined");
  assert.ok(content.includes("analyses:"), "analyses feed kind should be defined");
  assert.ok(content.includes("signals:"), "signals feed kind should be defined");

  // Verify paths
  assert.ok(content.includes('path: "/api/signals"'));
  assert.ok(content.includes('path: "/api/paper/portfolios"'));
});
