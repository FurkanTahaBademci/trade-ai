const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/instrument-detail.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const { groupEvaluations, dedupeBySource, kapSummaries, companyWords, ageInDays, ageLabel, analystFreshness } = loaded.exports;

let nextId = 1;
const evaluation = (overrides) => ({
  id: nextId++, source_type: "news", source_id: 1, tier: 1, impact_score: 50, summary: "", event_type: "contract",
  created_at: "2026-10-16T10:00:00Z", status: "succeeded", ...overrides,
});
const exclude = companyWords("THYAO", "TÜRK HAVA YOLLARI A.O.");

test("dedupeBySource keeps Tier 2 for the same source document", () => {
  const tier1 = evaluation({ source_id: 7, tier: 1, created_at: "2026-10-16T10:00:00Z" });
  const tier2 = evaluation({ source_id: 7, tier: 2, created_at: "2026-10-16T09:00:00Z" });
  const other = evaluation({ source_id: 8 });
  assert.deepEqual(dedupeBySource([tier1, other, tier2]).map((row) => row.id), [tier2.id, other.id]);
  // Aynı id farklı kaynak türünde ayrı belgedir.
  assert.equal(dedupeBySource([evaluation({ source_type: "kap", source_id: 7 }), tier1]).length, 2);
});

test("groupEvaluations merges the same event reported by different sources", () => {
  const rows = [
    evaluation({ source_id: 1, tier: 2, impact_score: 75, created_at: "2026-10-17T08:00:00Z", summary: "Brent petrolün jeopolitik gerilimler nedeniyle 110 dolar seviyesine yaklaşması, enerji ithalatçısı olan Türkiye'nin dengeleri üzerinde baskı oluşturuyor." }),
    evaluation({ source_id: 1, tier: 1, impact_score: 70, created_at: "2026-10-17T07:59:00Z", summary: "Brent petrol, Orta Doğu gerilimiyle 110 dolar seviyelerini test etti." }),
    evaluation({ source_id: 2, impact_score: 60, created_at: "2026-10-16T12:00:00Z", summary: "Türk Hava Yolları, CFM firmasından 300'den fazla LEAP-1B motoru alacağını duyurdu." }),
    evaluation({ source_id: 3, impact_score: 85, created_at: "2026-10-16T10:00:00Z", summary: "Türk Hava Yolları (THYAO), filosundaki 295 adet Boeing 737 MAX uçağı için CFM International ile motor tedarik anlaşması imzaladı." }),
    evaluation({ source_id: 4, impact_score: 60, created_at: "2026-10-16T09:00:00Z", summary: "Türk Hava Yolları, Teknik A.Ş. ve CFM International arasında 600'den fazla LEAP-1B motorunu kapsayan bir iş birliği yapıldı." }),
    evaluation({ source_type: "kap", source_id: 5, impact_score: 75, created_at: "2026-10-16T08:00:00Z", summary: "THY ve CFM International arasında 295 adede kadar uçak için motor temini, bakım hizmeti ve bakım merkezi kurulması konularında mutabakat zaptı imzalandı." }),
    evaluation({ source_id: 6, impact_score: 30, created_at: "2026-10-16T07:00:00Z", summary: "Brent petrol fiyatları, arz artışı beklentileriyle geriledi." }),
    evaluation({ source_type: "kap", source_id: 5, tier: 2, impact_score: 75, created_at: "2026-10-16T08:30:00Z", summary: "THY, CFM International ile B737 MAX filosu için motor tedariki, bakım hizmetleri ve THY Teknik bünyesinde yeni bir motor bakım merkezi kurulması konusunda mutabakat zaptı imzaladı." }),
  ];
  const groups = groupEvaluations(rows, exclude);
  assert.equal(groups.length, 3);
  const [brent, cfm, brentFall] = groups;
  assert.equal(brent.lead.tier, 2);
  assert.equal(brent.related.length, 0);
  assert.equal(cfm.lead.impact_score, 85);
  assert.equal(cfm.related.length, 3);
  // KAP belgesinin Tier 1 kopyası tamamen düşer, Tier 2 kopyası grupta kalır.
  assert.ok(cfm.related.some((row) => row.source_type === "kap" && row.tier === 2));
  assert.equal(brentFall.lead.source_id, 6);
});

test("groupEvaluations does not merge similar summaries days apart", () => {
  const summary = "CFM International ile motor tedarik anlaşması imzalandı ve bakım merkezi kuruluyor.";
  const groups = groupEvaluations([
    evaluation({ source_id: 1, summary, created_at: "2026-10-16T10:00:00Z" }),
    evaluation({ source_id: 2, summary, created_at: "2026-10-01T10:00:00Z" }),
  ], exclude);
  assert.equal(groups.length, 2);
});

test("kapSummaries maps disclosure index to the best AI summary", () => {
  const map = kapSummaries([
    evaluation({ source_type: "kap", source_id: 99, tier: 1, summary: "Kısa özet" }),
    evaluation({ source_type: "kap", source_id: 99, tier: 2, summary: " Ayrıntılı özet " }),
    evaluation({ source_type: "news", source_id: 100, summary: "Haber" }),
    evaluation({ source_type: "kap", source_id: 101, summary: null }),
  ]);
  assert.deepEqual([...map.entries()], [[99, "Ayrıntılı özet"]]);
});

test("analyst freshness separates consensus window from all records", () => {
  const today = new Date(2026, 9, 17);
  const rec = (institution, date) => ({ institution, recommendation_date: date });
  const freshness = analystFreshness([rec("Hsbc", "2026-08-05"), rec("İş Yatırım", "2026-04-24"), rec("Tacirler", "2026-03-05"), rec("HSBC", "2025-12-01")], today);
  assert.equal(freshness.newestAgeDays, 73);
  assert.equal(freshness.inWindow, 2);
  assert.equal(freshness.stale, 2);
  assert.equal(freshness.institutions, 3);
  assert.deepEqual(analystFreshness([], today), { newestAgeDays: null, inWindow: 0, stale: 0, institutions: 0 });
  assert.equal(ageInDays("2026-10-16", today), 1);
  assert.equal(ageLabel(0), "bugün");
  assert.equal(ageLabel(1), "dün");
  assert.equal(ageLabel(73), "73 gün önce");
});
