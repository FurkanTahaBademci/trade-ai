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

const account = require(path.resolve(__dirname, "../src/lib/account.ts"));
const { apiGet } = require(path.resolve(__dirname, "../src/lib/api.ts"));
const { safeNextPath } = require(path.resolve(__dirname, "../src/lib/admin-auth.ts"));

test("personal and admin endpoints are recognised as private", () => {
  for (const privatePath of ["/api/me", "/api/me/watchlist", "/api/auth/login", "/api/admin/users?limit=5", "/api/me?x=1"]) {
    assert.equal(account.isPrivateApiPath(privatePath), true, privatePath);
  }
  for (const publicPath of ["/api/markets", "/api/paper/portfolios", "/api/metrics", "/api/authors", "/health"]) {
    assert.equal(account.isPrivateApiPath(publicPath), false, publicPath);
  }
});

test("the shared apiGet cache refuses private endpoints before any fetch", async () => {
  const originalFetch = global.fetch;
  let calls = 0;
  global.fetch = async () => { calls += 1; return new Response("{}"); };
  try {
    await assert.rejects(() => apiGet("/api/me/watchlist", null, { revalidate: 30 }), /kişisel/);
    await assert.rejects(() => apiGet("/api/admin/users", null), /kişisel/);
    assert.equal(calls, 0);
  } finally {
    global.fetch = originalFetch;
  }
});

test("API errors keep code and message from structured, string and validation bodies", () => {
  assert.deepEqual(account.parseApiError({ detail: { code: "email_not_verified", message: "Doğrula" } }, 403), { ok: false, status: 403, code: "email_not_verified", message: "Doğrula" });
  assert.deepEqual(account.parseApiError({ detail: "Bulunamadı" }, 404), { ok: false, status: 404, message: "Bulunamadı" });
  assert.equal(account.parseApiError({ detail: [{ loc: ["body"], msg: "x" }] }, 422).message, "Gönderilen bilgiler geçersiz.");
  assert.match(account.parseApiError(null, 502).message, /ulaşılamıyor/);
  assert.match(account.parseApiError(null, 429).message, /Çok fazla/);
});

test("session cookie lifetime follows the server expiry and stays bounded", () => {
  const now = Date.UTC(2026, 9, 29, 12, 0, 0);
  assert.equal(account.sessionCookieMaxAge(new Date(now + 3600_000).toISOString(), now), 3600);
  assert.equal(account.sessionCookieMaxAge(new Date(now - 1000).toISOString(), now), 0);
  assert.equal(account.sessionCookieMaxAge("geçersiz", now), 30 * 24 * 60 * 60);
  assert.equal(account.sessionCookieMaxAge(new Date(now + 10 * 365 * 86400_000).toISOString(), now), 365 * 24 * 60 * 60);
});

test("initials and device names are short and readable", () => {
  assert.equal(account.accountInitials({ display_name: "ayşe kaya", email: "a@example.com" }), "AK");
  assert.equal(account.accountInitials({ display_name: "", email: "mehmet@example.com" }), "ME");
  assert.equal(account.describeUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"), "Chrome · Windows");
  assert.equal(account.describeUserAgent("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1"), "Safari · iOS");
  assert.equal(account.describeUserAgent(null), "Bilinmeyen cihaz");
});

test("login redirect falls back per role and never leaves the site", () => {
  assert.equal(safeNextPath("", "/"), "/");
  assert.equal(safeNextPath(undefined, "/sistem"), "/sistem");
  assert.equal(safeNextPath("https://evil.example/x", "/"), "/");
  assert.equal(safeNextPath("//evil.example", "/"), "/");
  assert.equal(safeNextPath("/giris?next=/hesap", "/"), "/");
  assert.equal(safeNextPath("/hesap?tab=1", "/"), "/hesap?tab=1");
});

test("account state distinguishes an invalid session from an unreachable API", async () => {
  const originalFetch = global.fetch;
  try {
    global.fetch = async (url, init) => {
      assert.equal(url, "http://api.test/api/me");
      assert.equal(init.headers.Authorization, "Bearer t1");
      return new Response(JSON.stringify({ id: 1, email: "a@example.com", display_name: "A", role: "user" }), { status: 200 });
    };
    assert.equal((await account.fetchAccountState("t1", "http://api.test")).state, "valid");
    global.fetch = async () => new Response("{}", { status: 401 });
    assert.equal((await account.fetchAccountState("t1", "http://api.test")).state, "invalid");
    global.fetch = async () => new Response("{}", { status: 503 });
    assert.equal((await account.fetchAccountState("t1", "http://api.test")).state, "error");
    global.fetch = async () => { throw new Error("ECONNREFUSED"); };
    assert.equal((await account.fetchAccountState("t1", "http://api.test")).state, "error");
  } finally {
    global.fetch = originalFetch;
  }
});
