const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/build-info.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const { fullVersion, versionLabel, versionSkew } = loaded.exports;

test("fullVersion appends the commit as SemVer build metadata", () => {
  assert.equal(fullVersion("0.3.0", ""), "0.3.0");
  assert.equal(fullVersion("0.3.0", "abc1234"), "0.3.0+abc1234");
  assert.equal(versionLabel("0.3.0"), "v0.3.0");
});

test("versionSkew ignores build metadata and missing API version", () => {
  assert.equal(versionSkew("0.3.0", "0.3.0"), null);
  assert.equal(versionSkew("0.3.0", "0.3.0+abc1234"), null);
  assert.equal(versionSkew("0.3.0", null), null);
  assert.equal(versionSkew("0.3.0", "0.2.0"), "Web v0.3.0 · API v0.2.0");
});
