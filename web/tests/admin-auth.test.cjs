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

const auth = load("../src/lib/admin-auth.ts");
const limiter = load("../src/lib/login-rate-limit.ts");

const env = { NODE_ENV: "production", WEB_ADMIN_USERNAME: "operator", WEB_ADMIN_PASSWORD: "strong-secret" };
const now = Date.UTC(2026, 9, 8, 12, 0, 0);

test("development stays open unless web auth is explicitly configured", () => {
  assert.equal(auth.adminAuthState(undefined, { NODE_ENV: "development" }), "disabled");
  assert.equal(auth.adminAuthState(undefined, { NODE_ENV: "development", WEB_ADMIN_PASSWORD: "secret" }), "unauthorized");
});

test("production fails closed when credentials are missing", () => {
  assert.equal(auth.adminAuthState(undefined, { NODE_ENV: "production" }), "misconfigured");
  assert.equal(auth.verifyCredentials("admin", "", { NODE_ENV: "production" }), false);
  assert.throws(() => auth.createSessionToken({ NODE_ENV: "production" }));
});

test("credentials are checked exactly", () => {
  assert.equal(auth.verifyCredentials("operator", "strong-secret", env), true);
  assert.equal(auth.verifyCredentials("operator", "wrong", env), false);
  assert.equal(auth.verifyCredentials("admin", "strong-secret", env), false);
  assert.equal(auth.verifyCredentials("operator", "strong-secret ", env), false);
});

test("admin API token is a backward-compatible password fallback", () => {
  const fallback = { NODE_ENV: "production", ADMIN_API_TOKEN: "existing-token" };
  assert.equal(auth.verifyCredentials("admin", "existing-token", fallback), true);
});

test("a fresh session token authorizes until it expires", () => {
  const token = auth.createSessionToken(env, now);
  assert.equal(auth.adminAuthState(token, env, now), "authorized");
  const almost = now + (auth.ADMIN_SESSION_TTL_SECONDS - 1) * 1000;
  assert.equal(auth.adminAuthState(token, env, almost), "authorized");
  const expired = now + auth.ADMIN_SESSION_TTL_SECONDS * 1000;
  assert.equal(auth.adminAuthState(token, env, expired), "unauthorized");
});

test("missing, malformed and tampered tokens are rejected", () => {
  const token = auth.createSessionToken(env, now);
  const [payload, signature] = token.split(".");
  const forged = Buffer.from(JSON.stringify({ u: "operator", exp: 9999999999 })).toString("base64url");
  for (const candidate of [undefined, "", "abc", `${payload}.`, `${payload}.${signature}.x`, `${forged}.${signature}`, `${payload}.${signature.slice(0, -2)}AA`]) {
    assert.equal(auth.adminAuthState(candidate, env, now), "unauthorized", String(candidate));
  }
});

test("changing the password or username invalidates existing sessions", () => {
  const token = auth.createSessionToken(env, now);
  assert.equal(auth.adminAuthState(token, { ...env, WEB_ADMIN_PASSWORD: "rotated-secret" }, now), "unauthorized");
  assert.equal(auth.adminAuthState(token, { ...env, WEB_ADMIN_USERNAME: "someone" }, now), "unauthorized");
});

test("post-login redirect only allows same-site paths", () => {
  assert.equal(auth.safeNextPath("/sistem?tab=1"), "/sistem?tab=1");
  assert.equal(auth.safeNextPath("/backtest"), "/backtest");
  for (const unsafe of [undefined, "", "sistem", "//evil.example", "/\\evil.example", "https://evil.example", "/giris", "/giris?next=/x"]) {
    assert.equal(auth.safeNextPath(unsafe), "/sistem", String(unsafe));
  }
});

test("login lockout applies per client and expires after the window", () => {
  const store = new Map();
  for (let i = 0; i < limiter.LOGIN_MAX_FAILURES_PER_CLIENT - 1; i += 1) limiter.recordFailure(store, "1.1.1.1", now);
  assert.equal(limiter.lockoutRemainingMs(store, "1.1.1.1", now), 0);
  limiter.recordFailure(store, "1.1.1.1", now);
  assert.ok(limiter.lockoutRemainingMs(store, "1.1.1.1", now) > 0);
  assert.equal(limiter.lockoutRemainingMs(store, "2.2.2.2", now), 0);
  assert.equal(limiter.lockoutRemainingMs(store, "1.1.1.1", now + limiter.LOGIN_WINDOW_MS), 0);
});

test("global lockout stops attackers rotating client addresses", () => {
  const store = new Map();
  for (let i = 0; i < limiter.LOGIN_MAX_FAILURES_GLOBAL; i += 1) limiter.recordFailure(store, `10.0.0.${i}`, now);
  assert.ok(limiter.lockoutRemainingMs(store, "203.0.113.9", now) > 0);
});

test("successful login clears the client's failures", () => {
  const store = new Map();
  for (let i = 0; i < limiter.LOGIN_MAX_FAILURES_PER_CLIENT; i += 1) limiter.recordFailure(store, "1.1.1.1", now);
  limiter.clearFailures(store, "1.1.1.1");
  assert.equal(limiter.lockoutRemainingMs(store, "1.1.1.1", now), 0);
});
