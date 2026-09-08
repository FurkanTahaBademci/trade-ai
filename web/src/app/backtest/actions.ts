"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { backtestFields, validateBacktestForm, type BacktestField, type BacktestFormState } from "@/lib/backtest-form";

export async function createBacktestAction(_previous: BacktestFormState, formData: FormData): Promise<BacktestFormState> {
  const values = Object.fromEntries(Object.keys(backtestFields).map((name) => [name, String(formData.get(name) ?? "")])) as BacktestFormState["values"];
  const errors = validateBacktestForm(values);
  if (Object.keys(errors).length) return { values, errors, message: "İşaretli alanları kontrol edin." };
  const payload = {
    start_date: values.start_date, end_date: values.end_date,
    initial_cash: Number(values.initial_cash), entry_score: Number(values.entry_score), exit_score: Number(values.exit_score),
    max_positions: Number(values.max_positions), max_position_weight: Number(values.max_position_weight) / 100,
    fee_rate: Number(values.fee_rate) / 100, slippage_rate: Number(values.slippage_rate) / 100,
  };
  let runId: number;
  try {
    const response = await fetch(`${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/backtests`, {
      method: "POST", cache: "no-store",
      headers: { "Content-Type": "application/json", "X-Admin-Token": process.env.ADMIN_API_TOKEN ?? "" },
      body: JSON.stringify(payload),
    });
    const body = await response.json().catch(() => null) as { id?: number; detail?: unknown } | null;
    if (!response.ok || !Number.isSafeInteger(body?.id) || !body?.id || body.id < 1) {
      if (Array.isArray(body?.detail)) {
        for (const detail of body.detail) {
          const name = Array.isArray(detail?.loc) ? detail.loc.at(-1) : null;
          if (typeof name === "string" && Object.hasOwn(backtestFields, name)) errors[name as BacktestField] = "Bu alan için geçerli bir değer girin.";
        }
      }
      return { values, errors, message: response.status === 422 ? "Ayarları kontrol edin; seçilen aralık veya değerler kabul edilmedi." : "Koşu kaydedilemedi. Lütfen tekrar deneyin." };
    }
    runId = body.id;
  } catch {
    return { values, message: "Servise ulaşılamadı. Ayarlarınız korundu; tekrar deneyebilirsiniz." };
  }
  revalidatePath("/backtest");
  redirect(`/backtest?run=${runId}`);
}
