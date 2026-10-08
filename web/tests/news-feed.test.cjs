const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/news-feed.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const { newsFeedCursor } = loaded.exports;

const item = { id: 42, published_at: "2026-10-01T12:00:00Z" };

test("smart news pagination advances by the number of loaded items", () => {
  assert.deepEqual(newsFeedCursor("smart", item, 12), { offset: 12 });
  assert.deepEqual(newsFeedCursor("smart", item, 24), { offset: 24 });
});

test("chronological news pagination keeps its stable timestamp and id cursor", () => {
  assert.deepEqual(newsFeedCursor("chronological", item, 24), {
    before: item.published_at,
    before_id: item.id,
  });
});
