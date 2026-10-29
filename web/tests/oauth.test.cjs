const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const ts = require("typescript");

require.extensions[".ts"] = function (mod, filename) {
  const compiled = ts.transpileModule(readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });
  mod._compile(compiled.outputText, filename);
};

const oauth = require(path.resolve(__dirname, "../src/lib/oauth.ts"));

const STATE = { state: "s".repeat(32), verifier: "v".repeat(64), nonce: "n".repeat(22), mode: "signup", next: "/portfoylerim", invite: "ABCD-EFGH-JKLM", terms: true };

test("OAuth state round-trips through the cookie value", () => {
  const raw = oauth.encodeOAuthState(STATE);
  assert.match(raw, /^[A-Za-z0-9_-]+$/);
  assert.deepEqual(oauth.decodeOAuthState(raw), STATE);
});

test("tampered or incomplete cookies are rejected", () => {
  assert.equal(oauth.decodeOAuthState(undefined), null);
  assert.equal(oauth.decodeOAuthState("not-base64-json"), null);
  assert.equal(oauth.decodeOAuthState(oauth.encodeOAuthState({ ...STATE, verifier: "" })), null);
  const odd = oauth.decodeOAuthState(Buffer.from(JSON.stringify({ ...STATE, mode: "admin", terms: "yes" })).toString("base64url"));
  assert.equal(odd.mode, "login");
  assert.equal(odd.terms, false);
  assert.equal(oauth.decodeOAuthState("x".repeat(5000)), null);
});

test("error codes map to fixed pages and messages", () => {
  assert.equal(oauth.googleErrorPath("login", "link_required"), "/giris?google=link_required");
  assert.equal(oauth.googleErrorPath("login", "signup_required"), "/kayit?google=signup_required");
  assert.equal(oauth.googleErrorPath("signup", "google_failed"), "/kayit?google=google_failed");
  const linked = oauth.googleErrorPath("link", "identity_in_use");
  assert.ok(linked.startsWith("/hesap?result=error&message="));
  assert.equal(decodeURIComponent(linked.split("message=")[1]), oauth.GOOGLE_MESSAGES.identity_in_use);
  // Bilinmeyen kod sabit genel mesaja düşer; URL'den gelen metin gösterilmez.
  assert.equal(oauth.googleMessage("<script>"), oauth.GOOGLE_MESSAGES.google_failed);
  assert.equal(oauth.googleMessage(undefined), undefined);
  assert.equal(oauth.parseGoogleMode("link"), "link");
  assert.equal(oauth.parseGoogleMode(null), "login");
});
