const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/theme.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const {
  THEME_STORAGE_KEY,
  resolveTheme,
  getStoredTheme,
  applyTheme,
} = loaded.exports;

test("THEME_STORAGE_KEY is trade-ai:theme", () => {
  assert.equal(THEME_STORAGE_KEY, "trade-ai:theme");
});

test("resolveTheme correctly resolves explicit and system preferences", () => {
  // Explicit preferences
  assert.equal(resolveTheme("light", true), "light");
  assert.equal(resolveTheme("light", false), "light");
  assert.equal(resolveTheme("dark", true), "dark");
  assert.equal(resolveTheme("dark", false), "dark");

  // System preferences
  assert.equal(resolveTheme("system", true), "dark");
  assert.equal(resolveTheme("system", false), "light");

  // Null, undefined or unknown fall back to system preference
  assert.equal(resolveTheme(null, true), "dark");
  assert.equal(resolveTheme(null, false), "light");
  assert.equal(resolveTheme(undefined, true), "dark");
  assert.equal(resolveTheme(undefined, false), "light");
  assert.equal(resolveTheme("invalid", true), "dark");
  assert.equal(resolveTheme("invalid", false), "light");
});

test("applyTheme persists to localStorage and sets data-theme on documentElement", () => {
  const store = {};
  const mockDoc = {
    attributes: {},
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
    getAttribute(name) {
      return this.attributes[name];
    },
  };

  const originalWindow = global.window;
  const originalDoc = global.document;

  global.window = {
    localStorage: {
      getItem(key) {
        return store[key] ?? null;
      },
      setItem(key, value) {
        store[key] = String(value);
      },
    },
    matchMedia(query) {
      return { matches: query.includes("dark") };
    },
    dispatchEvent() {
      return true;
    },
  };
  global.document = {
    documentElement: mockDoc,
  };
  global.CustomEvent = class CustomEvent {
    constructor(name, init) {
      this.name = name;
      this.detail = init?.detail;
    }
  };

  try {
    // 1. Initial store should be system
    assert.equal(getStoredTheme(), "system");

    // 2. Apply light theme
    const resolvedLight = applyTheme("light");
    assert.equal(resolvedLight, "light");
    assert.equal(store[THEME_STORAGE_KEY], "light");
    assert.equal(mockDoc.getAttribute("data-theme"), "light");

    // 3. Apply dark theme
    const resolvedDark = applyTheme("dark");
    assert.equal(resolvedDark, "dark");
    assert.equal(store[THEME_STORAGE_KEY], "dark");
    assert.equal(mockDoc.getAttribute("data-theme"), "dark");

    // 4. getStoredTheme reflects applied theme
    assert.equal(getStoredTheme(), "dark");
  } finally {
    global.window = originalWindow;
    global.document = originalDoc;
  }
});
