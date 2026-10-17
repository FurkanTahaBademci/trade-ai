import type { Evaluation, Recommendation } from "./types";

// Hisse detay sayfasının saf yardımcıları: AI değerlendirmelerinin tekilleştirilmesi,
// KAP bildirimleri için AI özetleri ve analist hedeflerinin yaşı.

export type EvaluationGroup = { lead: Evaluation; related: Evaluation[] };

// Konsensüs hesabı yalnız bu kadar gün içindeki görüşleri kullanır (backend ile aynı pencere).
export const ANALYST_CONSENSUS_WINDOW_DAYS = 180;
// Bu yaştan eski en yeni hedef, konsensüs penceresinde olsa da uyarı tonunda gösterilir.
export const ANALYST_FRESH_DAYS = 90;

const STEM_LENGTH = 6;
const MIN_SHARED_TOKENS = 3;
const MIN_SHARED_RATIO = 0.3;
const SIMILAR_WINDOW_HOURS = 72;

// Haber özetlerinde olaydan bağımsız sık geçen sözcükler (kök ilk 6 harf üzerinden eşlenir).
const STOPWORDS = [
  "ve", "ile", "için", "bir", "bu", "şu", "da", "de", "ki", "mi", "olan", "olarak", "olduğu", "oldu", "arasında",
  "üzerinde", "kadar", "daha", "gibi", "çok", "en", "ilk", "son", "yeni", "yıl", "yılı", "ay", "gün", "milyon",
  "milyar", "yüzde", "şirket", "şirketi", "hisse", "hisseleri", "borsa", "bist", "istanbul", "açıkladı",
  "duyurdu", "bildirdi", "belirtti", "etti", "edildi", "yaptı", "yapıldı", "ise", "tarafından", "sonra", "önce",
  "ancak", "nedeniyle", "göre", "kapsamında", "konusunda",
].map((word) => word.slice(0, STEM_LENGTH));
const STOP_STEMS = new Set(STOPWORDS);

export function summaryStems(text: string | null | undefined, exclude: Iterable<string> = []): Set<string> {
  const excluded = new Set([...exclude].map((word) => word.toLocaleLowerCase("tr-TR").slice(0, STEM_LENGTH)));
  const stems = new Set<string>();
  for (const token of (text ?? "").toLocaleLowerCase("tr-TR").split(/[^\p{L}\p{N}]+/u)) {
    if (token.length < 3 || /^\p{N}+$/u.test(token)) continue;
    const stem = token.slice(0, STEM_LENGTH);
    if (!STOP_STEMS.has(stem) && !excluded.has(stem)) stems.add(stem);
  }
  return stems;
}

// Hisse kodu ve şirket adındaki sözcükler her özette geçtiği için benzerlikte sayılmaz.
export function companyWords(ticker: string, name?: string | null): string[] {
  const words = (name ?? "").split(/[^\p{L}\p{N}]+/u).filter((word) => word.length >= 3);
  return [ticker, ticker.slice(0, 3), ...words];
}

function better(a: Evaluation, b: Evaluation) {
  const impact = (a.impact_score ?? -1) - (b.impact_score ?? -1);
  if (impact) return impact > 0;
  if (a.tier !== b.tier) return a.tier > b.tier;
  return a.created_at > b.created_at;
}

// Aynı kaynak belgenin birden çok değerlendirmesi (Tier 1 + Tier 2, tekrar denemeler)
// tek kayda iner: Tier 2 varsa o, yoksa en yenisi. Giriş sırası korunur.
export function dedupeBySource(items: Evaluation[]): Evaluation[] {
  const best = new Map<string, Evaluation>();
  const order: string[] = [];
  for (const item of items) {
    const key = `${item.source_type}:${item.source_id}`;
    const current = best.get(key);
    if (!current) { best.set(key, item); order.push(key); continue; }
    if (item.tier > current.tier || (item.tier === current.tier && item.created_at > current.created_at)) best.set(key, item);
  }
  return order.map((key) => best.get(key)!);
}

// Farklı kaynaklardan gelen aynı olay (ör. bir anlaşmanın KAP bildirimi ve üç haberi)
// özet benzerliği ile gruplanır; grubun en yüksek etkili kaydı öne çıkar.
export function groupEvaluations(items: Evaluation[], exclude: Iterable<string> = []): EvaluationGroup[] {
  const unique = dedupeBySource(items);
  const excluded = [...exclude];
  const stems = unique.map((item) => summaryStems(item.summary, excluded));
  const times = unique.map((item) => new Date(item.created_at).getTime());
  const parent = unique.map((_, index) => index);
  const root = (index: number): number => (parent[index] === index ? index : (parent[index] = root(parent[index])));
  for (let i = 0; i < unique.length; i += 1) {
    for (let j = i + 1; j < unique.length; j += 1) {
      if (Math.abs(times[i] - times[j]) > SIMILAR_WINDOW_HOURS * 3_600_000) continue;
      const smaller = Math.min(stems[i].size, stems[j].size);
      if (!smaller) continue;
      let shared = 0;
      for (const stem of stems[i]) if (stems[j].has(stem)) shared += 1;
      if (shared >= MIN_SHARED_TOKENS && shared / smaller >= MIN_SHARED_RATIO) parent[root(j)] = root(i);
    }
  }
  const groups = new Map<number, Evaluation[]>();
  unique.forEach((item, index) => {
    const key = root(index);
    groups.set(key, [...(groups.get(key) ?? []), item]);
  });
  return [...groups.values()].map((members) => {
    const lead = members.reduce((best, item) => (better(item, best) ? item : best));
    return { lead, related: members.filter((item) => item !== lead) };
  });
}

// KAP bildirimi (disclosure_index) başına en iyi AI özeti: önce Tier 2, sonra en yeni.
export function kapSummaries(items: Evaluation[]): Map<number, string> {
  const out = new Map<number, string>();
  for (const item of dedupeBySource(items.filter((row) => row.source_type === "kap" && row.summary?.trim()))) {
    out.set(item.source_id, item.summary!.trim());
  }
  return out;
}

export function ageInDays(isoDate: string, today: Date): number {
  const day = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  const [year, month, date] = isoDate.slice(0, 10).split("-").map(Number);
  return Math.round((day - Date.UTC(year, month - 1, date)) / 86_400_000);
}

export function ageLabel(days: number): string {
  if (days <= 0) return "bugün";
  if (days === 1) return "dün";
  return `${days} gün önce`;
}

export type AnalystFreshness = { newestAgeDays: number | null; inWindow: number; stale: number; institutions: number };

export function analystFreshness(rows: Recommendation[], today: Date): AnalystFreshness {
  const ages = rows.map((row) => ageInDays(row.recommendation_date, today));
  const inWindow = ages.filter((age) => age <= ANALYST_CONSENSUS_WINDOW_DAYS).length;
  return {
    newestAgeDays: ages.length ? Math.min(...ages) : null,
    inWindow,
    stale: ages.length - inWindow,
    institutions: new Set(rows.map((row) => row.institution.toLocaleLowerCase("tr-TR"))).size,
  };
}
