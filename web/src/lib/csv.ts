/** Türkçe Excel uyumlu CSV: UTF-8 BOM, noktalı virgül ayracı, formül enjeksiyonu koruması. */

export const CSV_BOM = "﻿";
const FORMULA_PREFIX = /^ *[=+\-@\t\r]/;

export function sanitizeCell(value: string): string {
  return FORMULA_PREFIX.test(value) ? `'${value}` : value;
}

export function formatCell(value: string | number | boolean | null | undefined): string {
  if (value == null) return "";
  if (typeof value === "boolean") return value ? "Evet" : "Hayır";
  // Sayılar formül değildir (negatif dahil); ondalık ayracı virgül.
  if (typeof value === "number") return Number.isFinite(value) ? String(value).replace(".", ",") : "";
  return sanitizeCell(value);
}

function quote(cell: string): string {
  return /[";\r\n]/.test(cell) ? `"${cell.replace(/"/g, '""')}"` : cell;
}

export function buildCsv(headers: string[], rows: Array<Array<string | number | boolean | null | undefined>>): string {
  const lines = [headers.map((h) => quote(sanitizeCell(h))), ...rows.map((row) => row.map((cell) => quote(formatCell(cell))))];
  return CSV_BOM + lines.map((line) => line.join(";")).join("\r\n") + "\r\n";
}

export function downloadCsv(filename: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
