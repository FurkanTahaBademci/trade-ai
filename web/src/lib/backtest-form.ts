export const backtestFields = {
  start_date: { label: "Başlangıç", type: "date", value: "" },
  end_date: { label: "Bitiş", type: "date", value: "" },
  initial_cash: { label: "Başlangıç bakiyesi (TL)", type: "number", value: "1000000", min: 1, max: 1000000000, step: "0.01" },
  entry_score: { label: "Giriş skoru", type: "number", value: "75", min: 1, max: 100, step: "1" },
  exit_score: { label: "Çıkış skoru", type: "number", value: "40", min: 0, max: 99, step: "1" },
  max_positions: { label: "Pozisyon sayısı", type: "number", value: "10", min: 1, max: 100, step: "1" },
  max_position_weight: { label: "Pozisyon ağırlığı (%)", type: "number", value: "10", min: 0.01, max: 100, step: "0.01" },
  fee_rate: { label: "Komisyon (%)", type: "number", value: "0.10", min: 0, max: 5, step: "0.01" },
  slippage_rate: { label: "Fiyat kayması (%)", type: "number", value: "0.05", min: 0, max: 5, step: "0.01" },
} as const;

export type BacktestField = keyof typeof backtestFields;
export type BacktestFormState = { values: Record<BacktestField, string>; errors?: Partial<Record<BacktestField, string>>; message?: string };

export function validateBacktestForm(values: BacktestFormState["values"]) {
  const errors: NonNullable<BacktestFormState["errors"]> = {};
  for (const name of Object.keys(backtestFields) as BacktestField[]) {
    const field = backtestFields[name];
    if (field.type === "date") {
      const value = values[name];
      const parsed = new Date(`${value}T00:00:00Z`);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) errors[name] = "Geçerli bir tarih seçin.";
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
  return errors;
}
