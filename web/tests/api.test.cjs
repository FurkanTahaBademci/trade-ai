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

test("revalidated requests are served from the in-process cache, failures are not", async () => {
  const { apiGet } = loaded.exports;
  const calls = [];
  const originalFetch = global.fetch;
  let fail = true;
  global.fetch = async (url) => {
    calls.push(url);
    if (fail) return { ok: false, status: 503, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => ({ value: calls.length }) };
  };
  try {
    const failed = await apiGet("/cache-test", null, { revalidate: 60 });
    assert.equal(failed.ok, false);
    const callsAfterFailure = calls.length;
    fail = false;
    const first = await apiGet("/cache-test", null, { revalidate: 60 });
    const second = await apiGet("/cache-test", null, { revalidate: 60 });
    assert.equal(first.ok, true);
    assert.deepEqual(second.data, first.data);
    assert.equal(calls.length, callsAfterFailure + 1);
    await apiGet("/cache-test", null);
    assert.equal(calls.length, callsAfterFailure + 2);
  } finally {
    global.fetch = originalFetch;
  }
});
