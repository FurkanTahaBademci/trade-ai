import type { StrategyConfig } from "./types";

/** Strateji ayar formunun alanları; sıra formdaki sıradır. */
export const STRATEGY_FIELDS: { key: Exclude<keyof StrategyConfig, "rebalance_enabled">; label: string; hint: string; min: number; max: number; step: number }[] = [
  { key: "entry_score", label: "Giriş skoru", hint: "Bileşik skor bu değer ve üstündeyse alınır.", min: 50, max: 100, step: 1 },
  { key: "exit_score", label: "Çıkış skoru", hint: "Skor bunun altına düşünce satılır.", min: 0, max: 95, step: 1 },
  { key: "min_confidence", label: "En düşük güven", hint: "0–1 arası; sinyal güveni bunun altındaysa alınmaz.", min: 0, max: 1, step: 0.05 },
  { key: "min_coverage", label: "En az kaynak sayısı", hint: "Skoru besleyen bileşen sayısı (1–4).", min: 1, max: 4, step: 1 },
  { key: "max_positions", label: "En fazla pozisyon", hint: "Aynı anda tutulabilecek hisse sayısı.", min: 1, max: 30, step: 1 },
  { key: "max_new_entries_per_day", label: "Günlük en fazla yeni alım", hint: "Boş yerler günlere yayılır.", min: 1, max: 30, step: 1 },
  { key: "max_position_weight_pct", label: "Tek pozisyon tavanı (%)", hint: "Pozisyon sayısı × tavan %100'ü aşamaz.", min: 0.5, max: 50, step: 0.5 },
  { key: "max_sector_weight_pct", label: "Sektör tavanı (%)", hint: "0 = sınırsız.", min: 0, max: 100, step: 1 },
  { key: "stop_loss_pct", label: "Zarar-kes (%)", hint: "Maliyete göre bu kadar düşünce satar; 0 = kapalı.", min: 0, max: 99, step: 1 },
  { key: "take_profit_pct", label: "Kâr-al (%)", hint: "Maliyete göre bu kadar yükselince satar; 0 = kapalı.", min: 0, max: 500, step: 1 },
  { key: "trailing_stop_pct", label: "Takip eden stop (%)", hint: "Zirveden bu kadar düşünce satar; 0 = kapalı.", min: 0, max: 99, step: 1 },
];

/** Form alanlarını strateji ayarına çevirir; hatalıysa kullanıcıya gösterilecek mesajı döner. */
export function parseStrategyConfig(get: (name: string) => unknown): { config: StrategyConfig } | { error: string } {
  const config: Partial<StrategyConfig> = {};
  for (const field of STRATEGY_FIELDS) {
    const raw = String(get(`cfg_${field.key}`) ?? "").trim().replace(",", ".");
    const value = Number(raw);
    if (!raw || !Number.isFinite(value) || value < field.min || value > field.max) {
      return { error: `${field.label} ${field.min}–${field.max} arasında olmalı.` };
    }
    config[field.key] = value;
  }
  config.rebalance_enabled = get("cfg_rebalance_enabled") === "on";
  const full = config as StrategyConfig;
  if (full.exit_score >= full.entry_score) return { error: "Çıkış skoru giriş skorundan küçük olmalı." };
  if (full.max_positions * full.max_position_weight_pct > 100) return { error: "En fazla pozisyon × tek pozisyon tavanı %100'ü aşamaz." };
  return { config: full };
}

/** Emir adedi/tutarı: Türkçe binlik ayıracı ve ondalık virgülü kabul eder. */
export function parseAmount(raw: unknown): number | null {
  const text = String(raw ?? "").trim().replace(/\s/g, "");
  if (!text) return null;
  const normalized = text.includes(",") ? text.replace(/\./g, "").replace(",", ".") : text.replace(/\.(?=\d{3}(\D|$))/g, "");
  const value = Number(normalized);
  return Number.isFinite(value) && value > 0 ? value : null;
}
