const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/turkish.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const {
  foldTurkish,
  normalizeTicker,
  matchesTurkishSearch,
  rankTurkishSearchMatch,
} = loaded.exports;

test("foldTurkish normalizes Turkish characters and casings", () => {
  assert.equal(foldTurkish(""), "");
  assert.equal(foldTurkish("İŞ BANKASI"), "is bankasi");
  assert.equal(foldTurkish("isctr"), "isctr");
  assert.equal(foldTurkish("İSCTR"), "isctr");
  assert.equal(foldTurkish("Şişecam"), "sisecam");
  assert.equal(foldTurkish("TÜPRAŞ"), "tupras");
  assert.equal(foldTurkish("Ereğli Demir Çelik"), "eregli demir celik");
  assert.equal(foldTurkish("GÜBRETAŞ"), "gubretas");
  assert.equal(foldTurkish("ÖZDERİCİ"), "ozderici");
});

test("normalizeTicker converts Turkish inputs to valid BIST uppercase ASCII", () => {
  assert.equal(normalizeTicker(""), "");
  assert.equal(normalizeTicker("isctr"), "ISCTR");
  assert.equal(normalizeTicker("İSCTR"), "ISCTR");
  assert.equal(normalizeTicker("ısctr"), "ISCTR");
  assert.equal(normalizeTicker("sise"), "SISE");
  assert.equal(normalizeTicker("thyao"), "THYAO");
  assert.equal(normalizeTicker("  tuprs  "), "TUPRS");
});

test("matchesTurkishSearch matches BIST tickers and names seamlessly", () => {
  // Direct ticker match (case-insensitive & folded)
  assert.equal(matchesTurkishSearch("isctr", "ISCTR", "TÜRKİYE İŞ BANKASI A.Ş."), true);
  assert.equal(matchesTurkishSearch("İSCTR", "ISCTR", "TÜRKİYE İŞ BANKASI A.Ş."), true);
  assert.equal(matchesTurkishSearch("sise", "SISE", "TÜRKİYE ŞİŞE VE CAM FABRİKALARI A.Ş."), true);
  assert.equal(matchesTurkishSearch("şişe", "SISE", "TÜRKİYE ŞİŞE VE CAM FABRİKALARI A.Ş."), true);
  assert.equal(matchesTurkishSearch("tuprs", "TUPRS", "TÜPRAŞ-TÜRKİYE PETROL RAFİNERİLERİ A.Ş."), true);
  assert.equal(matchesTurkishSearch("eregli", "EREGL", "EREĞLİ DEMİR VE ÇELİK FABRİKALARI T.A.Ş."), true);
  assert.equal(matchesTurkishSearch("ereğli", "EREGL", "EREĞLİ DEMİR VE ÇELİK FABRİKALARI T.A.Ş."), true);

  // Alias matches
  assert.equal(matchesTurkishSearch("thy", "THYAO", "TÜRK HAVA YOLLARI A.O."), true);
  assert.equal(matchesTurkishSearch("türk hava", "THYAO", "TÜRK HAVA YOLLARI A.O."), true);
  assert.equal(matchesTurkishSearch("tüpraş", "TUPRS", "TÜPRAŞ"), true);
  assert.equal(matchesTurkishSearch("garanti", "GARAN", "TÜRKİYE GARANTİ BANKASI A.Ş."), true);
  assert.equal(matchesTurkishSearch("koç", "KCHOL", "KOÇ HOLDİNG A.Ş."), true);
  assert.equal(matchesTurkishSearch("yapı kredi", "YKBNK", "YAPI VE KREDİ BANKASI A.Ş."), true);
  assert.equal(matchesTurkishSearch("erdemir", "EREGL", "EREĞLİ DEMİR ÇELİK"), true);

  // Non-matches
  assert.equal(matchesTurkishSearch("xyzqwe", "ISCTR", "TÜRKİYE İŞ BANKASI"), false);
});

test("rankTurkishSearchMatch prioritizes exact and prefix ticker matches", () => {
  const rankExact = rankTurkishSearchMatch("ISCTR", "ISCTR", "TÜRKİYE İŞ BANKASI A.Ş.");
  const rankPrefix = rankTurkishSearchMatch("IS", "ISCTR", "TÜRKİYE İŞ BANKASI A.Ş.");
  const rankName = rankTurkishSearchMatch("BANKASI", "ISCTR", "TÜRKİYE İŞ BANKASI A.Ş.");

  assert.equal(rankExact, 0);
  assert.equal(rankPrefix, 1);
  assert.ok(rankPrefix < rankName);
});
