const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const file = path.resolve(__dirname, "../src/lib/kap-body.ts");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const loaded = new Module(file, module);
loaded._compile(compiled.outputText, file);
const { parseKapBody, disclosureHeadline } = loaded.exports;

// Gerçek bir KAP "Özel Durum Açıklaması (Genel)" bildiriminin temizlenmiş metni.
const MATERIAL_EVENT = [
  "Özel Durum Açıklaması (Genel)",
  "Yapılan Açıklama Güncelleme mi?",
  "Hayır",
  "Konuya İlişkin Daha Önce Yapılan Açıklamanın Tarihi",
  "-",
  "Bildirim İçeriği",
  "Açıklamalar",
  "Bankamız, Dünya Bankası ile 200 milyon Avro tutarındaki kredi anlaşmasını 5 Eylül 2026 tarihinde imzalamıştır.",
].join("\n");

test("label/value lines become one definition list, prose stays paragraph", () => {
  assert.deepEqual(parseKapBody(MATERIAL_EVENT), [
    { kind: "heading", text: "Özel Durum Açıklaması (Genel)" },
    {
      kind: "fields",
      items: [
        { label: "Yapılan Açıklama Güncelleme mi?", value: "Hayır" },
        { label: "Konuya İlişkin Daha Önce Yapılan Açıklamanın Tarihi", value: "-" },
      ],
    },
    { kind: "heading", text: "Bildirim İçeriği" },
    { kind: "heading", text: "Açıklamalar" },
    {
      kind: "paragraph",
      text: "Bankamız, Dünya Bankası ile 200 milyon Avro tutarındaki kredi anlaşmasını 5 Eylül 2026 tarihinde imzalamıştır.",
    },
  ]);
});

test("general assembly fields pair dates, times and short text values", () => {
  const blocks = parseKapBody(
    "Genel Kurul Çağrısı\nGenel Kurul Tipi\nOlağan Genel Kurul\nGenel Kurul Tarihi\n27.10.2026\nGenel Kurul Saati\n14:00\nŞehir\nISPARTA",
  );
  assert.deepEqual(blocks[0], { kind: "heading", text: "Genel Kurul Çağrısı" });
  assert.deepEqual(
    blocks[1].items.map((item) => [item.label, item.value]),
    [
      ["Genel Kurul Tipi", "Olağan Genel Kurul"],
      ["Genel Kurul Tarihi", "27.10.2026"],
      ["Genel Kurul Saati", "14:00"],
      ["Şehir", "ISPARTA"],
    ],
  );
});

test("flattened table headers are not paired with each other", () => {
  const blocks = parseKapBody(
    "Teklif Edilen\nNakit Kar Payı Hak Kullanım Tarihi (1)\nKesinleşen\nÖdeme Tarihi (3)\nKayıt Tarihi (4)\n3. Dönem Kârı\n8.008.448.767\n7. Genel Kanuni Yedek Akçe ( - )\n8. Net Dağıtılabilir Dönem Karı",
  );
  const pairs = blocks.filter((block) => block.kind === "fields").flatMap((block) => block.items);
  assert.deepEqual(pairs, [{ label: "3. Dönem Kârı", value: "8.008.448.767" }]);
});

test("empty or missing text yields no blocks", () => {
  assert.deepEqual(parseKapBody(""), []);
  assert.deepEqual(parseKapBody(null), []);
});

test("tab headline combines tickers and disclosure subject", () => {
  assert.equal(
    disclosureHeadline({ subject: "Kar Payı Dağıtım İşlemlerine İlişkin Bildirim", summary: null, kap_title: "GÜBRE FABRİKALARI T.A.Ş.", ticker_codes: ["GUBRF"] }),
    "GUBRF · Kar Payı Dağıtım İşlemlerine İlişkin Bildirim",
  );
  assert.equal(
    disclosureHeadline({ subject: null, summary: null, kap_title: "KAMUYU AYDINLATMA PLATFORMU", ticker_codes: [] }),
    "KAMUYU AYDINLATMA PLATFORMU",
  );
});
