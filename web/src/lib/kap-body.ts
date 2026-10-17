/**
 * KAP bildirim metnini (satır satır düz metin) okunabilir bloklara ayırır.
 *
 * KAP formları "kısa etiket satırı + değer satırı" kalıbında gelir
 * ("Yapılan Açıklama Güncelleme mi?" / "Hayır"). Bu çiftler tanım listesi,
 * uzun açıklamalar paragraf, kısa bölüm adları başlık olarak döner.
 */
export type KapBodyBlock =
  | { kind: "fields"; items: { label: string; value: string }[] }
  | { kind: "heading"; text: string }
  | { kind: "paragraph"; text: string };

const MAX_LABEL = 90;
const MAX_VALUE = 160;
const MAX_SHORT_VALUE = 40;
const MAX_HEADING = 60;

// KAP formlarında değer içermeyen bölüm başlıkları; değer sanılmamalı.
const SECTION_HEADINGS = new Set([
  "Özet Bilgi",
  "Bildirim İçeriği",
  "Açıklamalar",
  "Ek Açıklamalar",
  "Genel Kurul Çağrısı",
  "Gündem Maddeleri",
  "Ekler",
]);

const DATE = /^\d{2}[./]\d{2}[./]\d{4}( \d{2}:\d{2}(:\d{2})?)?$/;
const NUMBER = /^[-+(]?\d[\d.,]*\)?\s?(%|TL|TRY|USD|EUR|Adet|adet)?$/;
// Düzleşmiş tablo başlığı/satırı: "3. Dönem Kârı", "* Nakit", "Tarih (1)", "Oranı(%)".
const TABLE_HEADER = /^(\d+\.\s|\*)|\(\d\)$|\((%|TL|TRY)\)$|^EK:\s*\d+$/i;
const WORD_VALUES = /^(Evet|Hayır|Var|Yok|Yoktur|Görüşüldü|Görüşülmedi|Peşin|Taksitli|Ödenecek|Ödenmeyecek|-|TRY|TL|USD|EUR)$/i;

/** Satır kendi başına bir "değer" gibi mi görünüyor (tarih, sayı, evet/hayır)? */
function isPlainValue(line: string): boolean {
  return DATE.test(line) || NUMBER.test(line) || WORD_VALUES.test(line);
}

function isLabel(line: string): boolean {
  return (
    line.length <= MAX_LABEL &&
    !SECTION_HEADINGS.has(line) &&
    !isPlainValue(line) &&
    !/[.:;]$/.test(line) &&
    !/^(\(\d+\)|\*)/.test(line)
  );
}

function isValueFor(label: string, value: string | undefined): value is string {
  if (!value || SECTION_HEADINGS.has(value) || value.endsWith("?")) return false;
  if (isPlainValue(value)) return true;
  // Tablo sütun/satır başlığının değeri ancak sayı/tarih olabilir.
  if (TABLE_HEADER.test(label)) return false;
  // Soru biçimindeki etiketin (".. mi?") cevabı daha uzun olabilir.
  if (label.endsWith("?")) return value.length <= MAX_VALUE;
  return value.length <= MAX_SHORT_VALUE && !/[.:;]$/.test(value) && !TABLE_HEADER.test(value);
}

export function parseKapBody(text: string | null | undefined): KapBodyBlock[] {
  const lines = (text ?? "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const blocks: KapBodyBlock[] = [];
  const push = (block: KapBodyBlock) => {
    const last = blocks[blocks.length - 1];
    if (block.kind === "fields" && last?.kind === "fields") last.items.push(...block.items);
    else blocks.push(block);
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const next = lines[i + 1];
    if (isLabel(line) && isValueFor(line, next)) {
      push({ kind: "fields", items: [{ label: line, value: next }] });
      i += 1;
    } else if (SECTION_HEADINGS.has(line) || (line.length <= MAX_HEADING && !/[.:;,]$/.test(line) && !isPlainValue(line))) {
      push({ kind: "heading", text: line });
    } else {
      push({ kind: "paragraph", text: line });
    }
  }
  // Ardışık başlıklardan yalnız sonuncusu bölüm başlığıdır; öncekiler (değeri
  // olmayan tablo sütunları vb.) metin olarak kalır.
  return blocks.map((block, index) =>
    block.kind === "heading" && blocks[index + 1]?.kind === "heading" && !SECTION_HEADINGS.has(block.text)
      ? { kind: "paragraph", text: block.text }
      : block,
  );
}

/** Sekme başlığı: "GUBRF · Kar Payı Dağıtımı" (ticker yoksa yalnız başlık). */
export function disclosureHeadline(item: { subject: string | null; summary: string | null; kap_title: string; ticker_codes: string[] }): string {
  const title = (item.subject || item.summary || item.kap_title || "").trim();
  const tickers = item.ticker_codes.slice(0, 3).join(", ");
  return [tickers, title].filter(Boolean).join(" · ");
}
