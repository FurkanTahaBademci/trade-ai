const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/api.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const { isApiNotFound } = loaded.exports;

test("only an explicit upstream 404 is treated as a missing page", () => {
  assert.equal(isApiNotFound({ data: null, ok: false, error: "HTTP 404", status: 404 }), true);
  assert.equal(isApiNotFound({ data: null, ok: false, error: "HTTP 503", status: 503 }), false);
  assert.equal(isApiNotFound({ data: null, ok: false, error: "timeout" }), false);
  assert.equal(isApiNotFound({ data: {}, ok: true }), false);
});
