const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/admin-auth.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const { adminAuthState } = loaded.exports;

function basic(username, password) {
  return `Basic ${Buffer.from(`${username}:${password}`).toString("base64")}`;
}

test("development stays open unless web auth is explicitly configured", () => {
  assert.equal(adminAuthState(null, { NODE_ENV: "development" }), "disabled");
  assert.equal(adminAuthState(null, { NODE_ENV: "development", WEB_ADMIN_PASSWORD: "secret" }), "unauthorized");
});

test("production fails closed when credentials are missing", () => {
  assert.equal(adminAuthState(null, { NODE_ENV: "production" }), "misconfigured");
});

test("production accepts explicit credentials and rejects invalid ones", () => {
  const env = { NODE_ENV: "production", WEB_ADMIN_USERNAME: "operator", WEB_ADMIN_PASSWORD: "strong-secret" };
  assert.equal(adminAuthState(basic("operator", "strong-secret"), env), "authorized");
  assert.equal(adminAuthState(basic("operator", "wrong"), env), "unauthorized");
  assert.equal(adminAuthState("Bearer nope", env), "unauthorized");
});

test("admin API token is a backward-compatible production fallback", () => {
  const env = { NODE_ENV: "production", ADMIN_API_TOKEN: "existing-token" };
  assert.equal(adminAuthState(basic("admin", "existing-token"), env), "authorized");
});
