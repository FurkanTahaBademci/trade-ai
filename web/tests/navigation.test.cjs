const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const SRC = path.resolve(__dirname, "../src");
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (request, parent, isMain, options) {
  const mapped = request.startsWith("@/") ? path.join(SRC, request.slice(2)) : request;
  try {
    return originalResolve.call(this, mapped, parent, isMain, options);
  } catch (err) {
    if (err.code === "MODULE_NOT_FOUND") {
      try {
        return originalResolve.call(this, mapped + ".ts", parent, isMain, options);
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

const { NAV_ITEMS, NAV_GROUPS, isActiveRoute, searchPages } = require(path.join(SRC, "lib/navigation.ts"));
const { pageTitle } = require(path.join(SRC, "lib/page-title.ts"));
const { istanbulToday, todayAnchor } = require(path.join(SRC, "lib/calendar.ts"));

test("her menü grubu rotası bir menü öğesine karşılık gelir ve her öğe bir grupta", () => {
  const hrefs = new Set(NAV_ITEMS.map((item) => item.href));
  const grouped = NAV_GROUPS.flatMap((group) => group.routes);
  for (const route of grouped) assert.ok(hrefs.has(route), route);
  assert.equal(new Set(grouped).size, NAV_ITEMS.length);
});

test("girişli sayfalar kilitli işaretlenir", () => {
  const locked = NAV_ITEMS.filter((item) => item.locked).map((item) => item.href).sort();
  assert.deepEqual(locked, ["/backtest", "/sistem"]);
  // Backtest her hesaba, sistem yalnız yöneticiye açık.
  assert.deepEqual(Object.fromEntries(NAV_ITEMS.filter((item) => item.locked).map((item) => [item.href, item.locked])), { "/backtest": "account", "/sistem": "admin" });
});

test("sayfa araması Türkçe karakterden bağımsız ve anahtar kelimeyle çalışır", () => {
  assert.equal(searchPages("sinyal")[0].href, "/sinyaller");
  assert.equal(searchPages("takvim")[0].href, "/takvim");
  // Ad "portföy" ile başlayan kişisel sayfa öne çıkar; model portföy de listededir.
  assert.deepEqual(searchPages("portfoy").map((item) => item.href).slice(0, 2), ["/portfoylerim", "/portfoy"]);
  assert.equal(searchPages("model")[0].href, "/portfoy");
  assert.equal(searchPages("TEMETTÜ")[0].href, "/takvim");
  assert.equal(searchPages("tefas")[0].href, "/kurumsal");
  assert.deepEqual(searchPages("   "), []);
  assert.deepEqual(searchPages("zzzz"), []);
});

test("ad eşleşmesi anahtar kelime eşleşmesinden önce gelir", () => {
  assert.equal(searchPages("haber")[0].href, "/haberler");
  assert.ok(searchPages("a", 3).length <= 3);
});

test("aktif rota alt sayfaları kapsar ama ön ek benzerliğini kapsamaz", () => {
  assert.ok(isActiveRoute("/", "/"));
  assert.ok(!isActiveRoute("/", "/kap"));
  assert.ok(isActiveRoute("/kap", "/kap/123"));
  assert.ok(!isActiveRoute("/kap", "/kapali"));
  assert.ok(isActiveRoute("/piyasalar", "/piyasalar"));
});

test("sekme başlığı uzun metni kelime sınırında kısaltır", () => {
  assert.equal(pageTitle("  Kısa   başlık ", "Yedek"), "Kısa başlık");
  assert.equal(pageTitle("", "Yedek"), "Yedek");
  assert.equal(pageTitle(null, "Yedek"), "Yedek");
  const long = "Merkez Bankası politika faizini beklentilere paralel olarak sabit tuttu ve sıkı duruş vurgusunu sürdürdü";
  const short = pageTitle(long, "Yedek", 60);
  assert.ok(short.length <= 60, short);
  assert.ok(short.endsWith("…"));
  assert.ok(long.startsWith(short.slice(0, -1)));
});

test("takvimde bugün İstanbul gününe göre hesaplanır", () => {
  // 21:30 UTC, İstanbul'da (UTC+3) ertesi gün 00:30.
  assert.equal(istanbulToday(new Date("2026-10-16T21:30:00Z")), "2026-10-17");
  assert.equal(istanbulToday(new Date("2026-10-17T12:00:00Z")), "2026-10-17");
});

test("bugün işareti bugünün grubuna, yoksa sonraki ilk gruba yerleşir", () => {
  const dates = ["2026-10-01", "2026-10-15", "2026-10-20"];
  assert.deepEqual(todayAnchor(dates, "2026-10-15"), { date: "2026-10-15", exact: true });
  assert.deepEqual(todayAnchor(dates, "2026-10-17"), { date: "2026-10-20", exact: false });
  assert.equal(todayAnchor(dates, "2026-10-25"), null);
  assert.equal(todayAnchor([], "2026-10-25"), null);
});
