const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync, readdirSync, statSync } = require("node:fs");
const path = require("node:path");

// Sunucu bileşeni, "use client" modülünden bir değeri (sabit, yardımcı
// fonksiyon) çağıramaz: Next.js o değeri istemci referansına çevirir ve sayfa
// çalışırken "server error" verir. `next build` bunu yakalamaz; bu test yakalar.
// Bileşenler (büyük harfle başlayan, JSX'te kullanılan) ve tipler serbesttir.

const SRC = path.resolve(__dirname, "../src");
const USE_CLIENT = /^\s*(?:\/\/[^\n]*\n|\/\*[\s\S]*?\*\/\s*)*["']use client["']/;

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return walk(full);
    return /\.(ts|tsx)$/.test(name) ? [full] : [];
  });
}

function isComponentName(name) {
  return /^[A-Z][a-z]/.test(name) || /^[A-Z][A-Za-z0-9]*$/.test(name) && !/^[A-Z0-9_]+$/.test(name);
}

const files = walk(SRC).map((file) => ({ file, text: readFileSync(file, "utf8") }));
const clientValues = new Map();
for (const { file, text } of files) {
  if (!USE_CLIENT.test(text)) continue;
  const names = [...text.matchAll(/export\s+(?:async\s+)?(?:const|let|function)\s+([A-Za-z_$][\w$]*)/g)]
    .map((match) => match[1])
    .filter((name) => !isComponentName(name));
  if (names.length) {
    const specifier = "@/" + path.relative(SRC, file).replace(/\\/g, "/").replace(/\.(ts|tsx)$/, "");
    clientValues.set(specifier, names);
  }
}

test("sunucu modülleri 'use client' modüllerinden değer çağırmaz", () => {
  const violations = [];
  for (const { file, text } of files) {
    if (USE_CLIENT.test(text)) continue;
    for (const match of text.matchAll(/import\s*\{([^}]*)\}\s*from\s*["']([^"']+)["']/g)) {
      const values = clientValues.get(match[2]);
      if (!values) continue;
      const imported = match[1]
        .split(",")
        .map((part) => part.trim())
        .filter((part) => part && !part.startsWith("type "))
        .map((part) => part.split(/\s+as\s+/)[0].trim());
      // Hook'lar (useX) sunucu modülünde zaten kullanılamaz; yalnız istemci
      // modülleri onları içe aktarır, burada sayılmaz.
      const bad = imported.filter((name) => values.includes(name) && !/^use[A-Z]/.test(name));
      if (bad.length) violations.push(`${path.relative(SRC, file)} <- ${match[2]}: ${bad.join(", ")}`);
    }
  }
  assert.deepEqual(violations, []);
});

test("istemci modülü taraması bileşen olmayan dışa aktarımları bulur", () => {
  assert.ok(isComponentName("ScreenerTable"));
  assert.ok(!isComponentName("TABLE_COLUMNS"));
  assert.ok(!isComponentName("toTableRow"));
});
