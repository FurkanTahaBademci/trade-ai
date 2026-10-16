type NumberField = { label: string; type: "number"; value: string; min: number; max: number; step: string; group: FieldGroup };
type DateField = { label: string; type: "date"; value: string; group: FieldGroup };
type SelectField = { label: string; type: "select"; value: string; options: readonly (readonly [string, string])[]; group: FieldGroup };
export type FieldGroup = "general" | "threshold" | "basket" | "execution" | "weights";

export const fieldGroups: { key: FieldGroup; title: string; hint?: string }[] = [
  { key: "general", title: "Dönem ve strateji" },
  { key: "threshold", title: "Eşik stratejisi", hint: "Yalnız “Eşik” stratejisinde kullanılır." },
  { key: "basket", title: "Sıralama sepeti", hint: "Yalnız “Sıralama sepeti” stratejisinde kullanılır: her dengeleme gününde skoru en yüksek N likit hisse eşit ağırlıkla tutulur." },
  { key: "execution", title: "Yürütme ve maliyet" },
  { key: "weights", title: "Ağırlık simülasyonu", hint: "Skor, saklanan bileşen skorlarından bu ağırlıklarla yeniden hesaplanır. Canlı modelin ağırlıklarında bırakılırsa kayıtlı skor kullanılır." },
];

// Canlı bileşik skorun (model v3) bileşen ağırlıkları, yüzde.
export const LIVE_WEIGHTS = { weight_llm: "35", weight_fundamental: "28", weight_analyst: "22", weight_momentum: "15" } as const;
export const WEIGHT_COMPONENTS = { weight_llm: "llm", weight_fundamental: "fundamental", weight_analyst: "analyst", weight_momentum: "momentum" } as const;

export const backtestFields = {
  start_date: { label: "Başlangıç", type: "date", value: "", group: "general" },
  end_date: { label: "Bitiş", type: "date", value: "", group: "general" },
  strategy: { label: "Strateji", type: "select", value: "threshold", options: [["threshold", "Eşik: skor ≥ giriş al, < çıkış sat"], ["basket", "Sıralama sepeti: en yüksek skorlu N hisse"]], group: "general" },
  initial_cash: { label: "Başlangıç bakiyesi (TL)", type: "number", value: "1000000", min: 1, max: 1000000000, step: "0.01", group: "general" },
  entry_score: { label: "Giriş skoru", type: "number", value: "75", min: 1, max: 100, step: "1", group: "threshold" },
  // 6 aylık walk-forward'da eğitimin en iyi beş kombinasyonunun hepsi 55 kullandı.
  exit_score: { label: "Çıkış skoru", type: "number", value: "55", min: 0, max: 99, step: "1", group: "threshold" },
  max_positions: { label: "Pozisyon sayısı", type: "number", value: "10", min: 1, max: 100, step: "1", group: "threshold" },
  max_position_weight: { label: "Pozisyon ağırlığı (%)", type: "number", value: "10", min: 0.01, max: 100, step: "0.01", group: "threshold" },
  // Paper portföyle aynı varsayılanlar; 0 kuralı kapatır.
  stop_loss_pct: { label: "Zarar-kes (%) · 0 = kapalı", type: "number", value: "15", min: 0, max: 99, step: "0.1", group: "threshold" },
  max_new_entries_per_day: { label: "Günlük yeni pozisyon · 0 = sınırsız", type: "number", value: "3", min: 0, max: 100, step: "1", group: "threshold" },
  basket_size: { label: "Sepetteki hisse sayısı", type: "number", value: "20", min: 1, max: 100, step: "1", group: "basket" },
  basket_keep: { label: "Elde tutma sırası (ilk N)", type: "number", value: "40", min: 1, max: 200, step: "1", group: "basket" },
  rebalance_days: { label: "Dengeleme aralığı (işlem günü)", type: "number", value: "10", min: 1, max: 60, step: "1", group: "basket" },
  fee_rate: { label: "Komisyon (%)", type: "number", value: "0.10", min: 0, max: 5, step: "0.01", group: "execution" },
  slippage_rate: { label: "Fiyat kayması (%)", type: "number", value: "0.05", min: 0, max: 5, step: "0.01", group: "execution" },
  // Gerçekçi yürütme: tavan/taban eşiği, likidite alt sınırı ve isteğe bağlı rejim filtresi.
  price_limit_pct: { label: "Tavan/taban eşiği (%) · 0 = kapalı", type: "number", value: "9.5", min: 0, max: 99, step: "0.1", group: "execution" },
  min_avg_volume: { label: "Min. 20 günlük ort. hacim (mn TL)", type: "number", value: "20", min: 0, max: 100000, step: "1", group: "execution" },
  regime_ma_days: { label: "Rejim filtresi: XU100 N günlük ort. · 0 = kapalı", type: "number", value: "0", min: 0, max: 250, step: "1", group: "execution" },
  max_volatility_pct: { label: "Maks. günlük oynaklık (%) · 0 = kapalı", type: "number", value: "0", min: 0, max: 50, step: "0.1", group: "execution" },
  weight_llm: { label: "AI etkisi (%)", type: "number", value: LIVE_WEIGHTS.weight_llm, min: 0, max: 100, step: "1", group: "weights" },
  weight_fundamental: { label: "Temel analiz (%)", type: "number", value: LIVE_WEIGHTS.weight_fundamental, min: 0, max: 100, step: "1", group: "weights" },
  weight_analyst: { label: "Analist görüşü (%)", type: "number", value: LIVE_WEIGHTS.weight_analyst, min: 0, max: 100, step: "1", group: "weights" },
  weight_momentum: { label: "Momentum (%)", type: "number", value: LIVE_WEIGHTS.weight_momentum, min: 0, max: 100, step: "1", group: "weights" },
} as const satisfies Record<string, NumberField | DateField | SelectField>;

export type BacktestField = keyof typeof backtestFields;
export type BacktestFormState = { values: Record<BacktestField, string>; errors?: Partial<Record<BacktestField, string>>; message?: string };

export function validateBacktestForm(values: BacktestFormState["values"]) {
  const errors: NonNullable<BacktestFormState["errors"]> = {};
  for (const name of Object.keys(backtestFields) as BacktestField[]) {
    const field: NumberField | DateField | SelectField = backtestFields[name];
    if (field.type === "date") {
      const value = values[name];
      const parsed = new Date(`${value}T00:00:00Z`);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) errors[name] = "Geçerli bir tarih seçin.";
    } else if (field.type === "select") {
      if (!field.options.some(([option]) => option === values[name])) errors[name] = "Listeden bir seçenek seçin.";
    } else {
      const value = Number(values[name]);
      if (!values[name].trim() || !Number.isFinite(value) || value < field.min || value > field.max) errors[name] = `${field.label}: ${field.min}–${field.max} aralığında bir değer girin.`;
      else if (field.step === "1" && !Number.isInteger(value)) errors[name] = "Tam sayı girin.";
    }
  }
  if (!errors.start_date && !errors.end_date) {
    const days = (Date.parse(values.end_date) - Date.parse(values.start_date)) / 86400000;
    if (days < 0) errors.end_date = "Bitiş tarihi başlangıçtan önce olamaz.";
    else if (days > 3650) errors.end_date = "En fazla 10 yıllık bir aralık seçin.";
  }
  if (!errors.entry_score && !errors.exit_score && Number(values.exit_score) >= Number(values.entry_score)) errors.exit_score = "Çıkış skoru giriş skorundan küçük olmalı.";
  if (!errors.max_positions && !errors.max_position_weight && Number(values.max_positions) * Number(values.max_position_weight) > 100) errors.max_position_weight = "Pozisyon sayısı × ağırlık %100'ü geçemez.";
  if (!errors.basket_size && !errors.basket_keep && Number(values.basket_keep) < Number(values.basket_size)) errors.basket_keep = "Elde tutma sırası sepet boyutundan küçük olamaz.";
  const weightNames = Object.keys(WEIGHT_COMPONENTS) as (keyof typeof WEIGHT_COMPONENTS)[];
  if (weightNames.every((name) => !errors[name]) && weightNames.reduce((sum, name) => sum + Number(values[name]), 0) <= 0) errors.weight_llm = "En az bir bileşenin ağırlığı sıfırdan büyük olmalı.";
  return errors;
}

/** Ağırlıklar canlı modelinkiyle aynıysa null (kayıtlı skor kullanılır); değilse 0–1 ağırlıklar. */
export function componentWeights(values: BacktestFormState["values"]): Record<string, number> | null {
  const names = Object.keys(WEIGHT_COMPONENTS) as (keyof typeof WEIGHT_COMPONENTS)[];
  if (names.every((name) => Number(values[name]) === Number(LIVE_WEIGHTS[name]))) return null;
  return Object.fromEntries(names.map((name) => [WEIGHT_COMPONENTS[name], Number(values[name]) / 100]));
}
