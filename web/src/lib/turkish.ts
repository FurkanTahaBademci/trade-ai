/**
 * Turkce karakter folding, hisse senedi ticker normalizasyonu ve BIST arama takma adlari.
 */

export function foldTurkish(text: string): string {
  if (!text) return "";
  return text
    .replace(/İ/g, "i")
    .replace(/I/g, "i")
    .replace(/ı/g, "i")
    .replace(/ğ/g, "g")
    .replace(/Ğ/g, "g")
    .replace(/ü/g, "u")
    .replace(/Ü/g, "u")
    .replace(/ş/g, "s")
    .replace(/Ş/g, "s")
    .replace(/ö/g, "o")
    .replace(/Ö/g, "o")
    .replace(/ç/g, "c")
    .replace(/Ç/g, "c")
    .toLowerCase()
    .trim();
}

export function normalizeTicker(ticker: string): string {
  if (!ticker) return "";
  return ticker
    .trim()
    .replace(/i/g, "I")
    .replace(/İ/g, "I")
    .replace(/ı/g, "I")
    .toUpperCase();
}

/**
 * BIST popüler hisseleri ve yaygın Türkçe arama terimleri / kısaltmaları.
 */
export const BIST_SEARCH_ALIASES: Record<string, string[]> = {
  THYAO: ["thy", "turk hava yollari", "turk havayollari"],
  TUPRS: ["tupras", "turkiye petrol rafinerileri", "petrol"],
  SISE: ["sisecam", "sise cam", "turkiye sise ve cam", "sise"],
  ISCTR: ["is bankasi", "isbank", "is c", "is ctr"],
  GARAN: ["garanti", "garanti bbva", "garantibbva"],
  YKBNK: ["yapi kredi", "yapi ve kredi", "yapikredi"],
  KCHOL: ["koc", "koc holding", "koctas"],
  SAHOL: ["sabanci", "sabanci holding"],
  AKBNK: ["akbank"],
  BIMAS: ["bim", "bim magazalar", "bim market"],
  ASELS: ["aselsan", "savunma sanayi"],
  EREGL: ["eregli", "erdemir", "eregli demir celik"],
  KRDMD: ["kardemir", "karabuk demir celik"],
  FROTO: ["ford", "ford otosan"],
  TOASO: ["tofas", "turk otomobil fabrikasi"],
  ARCLK: ["arcelik", "beko"],
  PGSUS: ["pegasus", "havatas"],
  TCELL: ["turkcell"],
  TTKOM: ["turk telekom", "telekom"],
  ENJSA: ["enerjisa"],
  PETKM: ["petkim"],
  EKGYO: ["emlak konut", "emlak konut gyo"],
  VAKBN: ["vakifbank", "vakif"],
  HALKB: ["halkbank", "halk"],
  KOZAL: ["koza altin", "kozal"],
  KOZAA: ["koza madencilik"],
  SOKM: ["sok", "sok market", "sok marketler"],
  MGROS: ["migros"],
  HEKTS: ["hektas"],
  TAVHL: ["tav", "tav havalimanlari"],
  TKFEN: ["tekfen", "tekfen holding"],
  ALARK: ["alarko", "alarko holding"],
  VESTL: ["vestel", "vestel elektronik"],
  VESBE: ["vestel beyaz esya"],
  KONTR: ["kontrolmatik"],
  SMRTG: ["smart gunes", "smart"],
  EUPWR: ["europower", "europower enerji"],
  ASTOR: ["astor", "astor enerji"],
  OYAKC: ["oyak cimento", "oyak"],
  CIMSA: ["cimsa", "cimsa cimento"],
  CANTE: ["can2 termik", "cante"],
  ODAS: ["odas", "odas elektrik"],
  BERA: ["bera", "bera holding"],
  QUAGR: ["qua granite", "qua"],
};

/**
 * Arama sorgusunun hisse kodu, şirket adı veya takma adları ile eşleşip eşleşmediğini kontrol eder.
 */
export function matchesTurkishSearch(
  query: string,
  ticker: string,
  name?: string
): boolean {
  const qFold = foldTurkish(query);
  if (!qFold) return true;

  const tFold = foldTurkish(ticker);
  if (tFold.includes(qFold)) return true;

  if (name && foldTurkish(name).includes(qFold)) return true;

  const normT = normalizeTicker(ticker);
  const aliases = BIST_SEARCH_ALIASES[normT];
  if (aliases) {
    for (const alias of aliases) {
      const aFold = foldTurkish(alias);
      if (aFold.includes(qFold) || qFold.includes(aFold)) {
        return true;
      }
    }
  }

  return false;
}

/**
 * Eşleşme alaka düzeyine göre sıralama skoru (düşük sayı = daha öncelikli).
 */
export function rankTurkishSearchMatch(
  query: string,
  ticker: string,
  name?: string
): number {
  const qFold = foldTurkish(query);
  if (!qFold) return 0;

  const tFold = foldTurkish(ticker);
  if (tFold === qFold) return 0;
  if (tFold.startsWith(qFold)) return 1;
  if (tFold.includes(qFold)) return 2;

  const normT = normalizeTicker(ticker);
  const aliases = BIST_SEARCH_ALIASES[normT];
  if (aliases) {
    for (const alias of aliases) {
      const aFold = foldTurkish(alias);
      if (aFold === qFold) return 2;
      if (aFold.startsWith(qFold)) return 3;
    }
  }

  if (name) {
    const nFold = foldTurkish(name);
    if (nFold.startsWith(qFold)) return 3;
    if (nFold.includes(qFold)) return 4;
  }

  return 5;
}
