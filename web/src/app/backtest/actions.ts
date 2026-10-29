"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { backtestFields, componentWeights, validateBacktestForm, type BacktestField, type BacktestFormState } from "@/lib/backtest-form";
import { requireAdminRequest } from "@/lib/admin-request";
import { accountRequest, apiBase, sessionToken } from "@/lib/account-server";
import type { MyPortfolio } from "@/lib/types";

/** Hesapla girişliyse kişisel uç (kotalı), değilse yerleşik yöneticinin sistem ucu. */
async function backtestTarget(): Promise<{ url: string; headers: Record<string, string> }> {
  const token = await sessionToken();
  if (token) return { url: `${apiBase()}/api/me/backtests`, headers: { Authorization: `Bearer ${token}` } };
  await requireAdminRequest();
  return { url: `${apiBase()}/api/backtests`, headers: { "X-Admin-Token": process.env.ADMIN_API_TOKEN ?? "" } };
}

export async function createBacktestAction(_previous: BacktestFormState, formData: FormData): Promise<BacktestFormState> {
  const target = await backtestTarget();
  const values = Object.fromEntries(Object.keys(backtestFields).map((name) => [name, String(formData.get(name) ?? "")])) as BacktestFormState["values"];
  const errors = validateBacktestForm(values);
  if (Object.keys(errors).length) return { values, errors, message: "İşaretli alanları kontrol edin." };
  const payload = {
    start_date: values.start_date, end_date: values.end_date,
    initial_cash: Number(values.initial_cash), entry_score: Number(values.entry_score), exit_score: Number(values.exit_score),
    max_positions: Number(values.max_positions), max_position_weight: Number(values.max_position_weight) / 100,
    fee_rate: Number(values.fee_rate) / 100, slippage_rate: Number(values.slippage_rate) / 100,
    stop_loss_pct: Number(values.stop_loss_pct), max_new_entries_per_day: Number(values.max_new_entries_per_day),
    price_limit_pct: Number(values.price_limit_pct), min_avg_volume: Number(values.min_avg_volume) * 1_000_000,
    regime_ma_days: Number(values.regime_ma_days), max_volatility_pct: Number(values.max_volatility_pct),
    strategy: values.strategy, basket_size: Number(values.basket_size), basket_keep: Number(values.basket_keep),
    rebalance_days: Number(values.rebalance_days), component_weights: componentWeights(values),
  };
  let runId: number;
  try {
    const response = await fetch(target.url, {
      method: "POST", cache: "no-store",
      headers: { "Content-Type": "application/json", ...target.headers },
      body: JSON.stringify(payload),
    });
    const body = await response.json().catch(() => null) as { id?: number; detail?: unknown } | null;
    if (!response.ok || !Number.isSafeInteger(body?.id) || !body?.id || body.id < 1) {
      if (Array.isArray(body?.detail)) {
        for (const detail of body.detail) {
          const name = Array.isArray(detail?.loc) ? detail.loc.at(-1) : null;
          if (typeof name === "string" && Object.hasOwn(backtestFields, name)) errors[name as BacktestField] = "Bu alan için geçerli bir değer girin.";
          else if (Array.isArray(detail?.loc) && detail.loc.includes("component_weights")) errors.weight_llm = "Ağırlıkları kontrol edin.";
        }
      }
      // Kota ve aktif koşu sınırı: API'nin Türkçe mesajı gösterilir.
      const limitMessage = body?.detail && typeof body.detail === "object" && !Array.isArray(body.detail) ? (body.detail as { message?: unknown }).message : undefined;
      if (typeof limitMessage === "string") return { values, errors, message: limitMessage };
      return { values, errors, message: response.status === 422 ? "Ayarları kontrol edin; seçilen aralık veya değerler kabul edilmedi." : "Koşu kaydedilemedi. Lütfen tekrar deneyin." };
    }
    runId = body.id;
  } catch {
    return { values, message: "Servise ulaşılamadı. Ayarlarınız korundu; tekrar deneyebilirsiniz." };
  }
  revalidatePath("/backtest");
  redirect(`/backtest?run=${runId}`);
}

function runIdOf(formData: FormData): number {
  const id = Number(formData.get("run_id"));
  if (!Number.isSafeInteger(id) || id < 1) redirect("/backtest");
  return id;
}

async function requireToken(): Promise<string> {
  const token = await sessionToken();
  if (!token) redirect("/giris?next=/backtest");
  return token;
}

export async function startPaperFromBacktestAction(formData: FormData) {
  const runId = runIdOf(formData);
  const token = await requireToken();
  const result = await accountRequest<MyPortfolio>(`/api/me/backtests/${runId}/paper`, token, {
    body: { name: String(formData.get("name") ?? "").trim(), initial_cash: Number(formData.get("initial_cash")) || 1_000_000 },
  });
  if (!result.ok) redirect(`/backtest?run=${runId}&result=error&message=${encodeURIComponent(result.message)}`);
  redirect(`/portfoylerim/${result.data.id}?result=ok&message=${encodeURIComponent(`Backtest #${runId} ayarlarıyla strateji portföyü oluşturuldu.`)}`);
}

export async function deleteBacktestAction(formData: FormData) {
  const runId = runIdOf(formData);
  const token = await requireToken();
  const result = await accountRequest(`/api/me/backtests/${runId}`, token, { method: "DELETE" });
  if (!result.ok) redirect(`/backtest?run=${runId}&result=error&message=${encodeURIComponent(result.message)}`);
  revalidatePath("/backtest");
  redirect(`/backtest?result=ok&message=${encodeURIComponent(`Koşu #${runId} silindi.`)}`);
}
