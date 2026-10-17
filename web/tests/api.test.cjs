const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (request, parent, isMain, options) {
  try {
    return originalResolve.call(this, request, parent, isMain, options);
  } catch (err) {
    if (err.code === "MODULE_NOT_FOUND") {
      try {
        return originalResolve.call(this, request + ".ts", parent, isMain, options);
      } catch {}
    }
    throw err;
  }
};
require.extensions[".ts"] = function (mod, filename) {
  const compiled = ts.transpileModule(readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });
  mod._compile(compiled.outputText, filename);
};

const loaded = { exports: require(path.resolve(__dirname, "../src/lib/api.ts")) };
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

test("apiGet reports cache outcomes and in-flight waits to the metrics hook", async () => {
  const { apiGet } = loaded.exports;
  const key = Symbol.for("trade-ai.request-metrics");
  const outcomes = [];
  let waits = 0;
  globalThis[key] = { apiStart: () => { waits += 1; return () => {}; }, cacheOutcome: (item) => outcomes.push(item), collect: async () => null };
  const originalFetch = global.fetch;
  let release;
  global.fetch = () => new Promise((resolve) => { release = () => resolve({ ok: true, status: 200, json: async () => ({ ok: 1 }) }); });
  try {
    const first = apiGet("/hook-test", null, { revalidate: 60 });
    const second = apiGet("/hook-test", null, { revalidate: 60 });
    release();
    await Promise.all([first, second]);
    await apiGet("/hook-test", null, { revalidate: 60 });
    assert.deepEqual(outcomes, ["miss", "shared", "hit"]);
    // Yalnız uçuştaki isteğe bağlanan bekleme kancadan sayılır; fetch'in kendisi
    // request-metrics.cjs'deki fetch sarmalayıcısıyla ölçülür.
    assert.equal(waits, 1);
  } finally {
    global.fetch = originalFetch;
    delete globalThis[key];
  }
});
