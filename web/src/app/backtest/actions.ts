"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

function apiBase() {
  return process.env.API_INTERNAL_URL ?? "http://localhost:8000";
}

function numberValue(formData: FormData, name: string) {
  return Number(formData.get(name));
}

export async function createBacktestAction(formData: FormData) {
  const payload = {
    start_date: String(formData.get("start_date") ?? ""),
    end_date: String(formData.get("end_date") ?? ""),
    initial_cash: numberValue(formData, "initial_cash"),
    entry_score: numberValue(formData, "entry_score"),
    exit_score: numberValue(formData, "exit_score"),
    max_positions: numberValue(formData, "max_positions"),
    max_position_weight: numberValue(formData, "max_position_weight") / 100,
    fee_rate: numberValue(formData, "fee_rate") / 100,
    slippage_rate: numberValue(formData, "slippage_rate") / 100,
  };
  let destination = "/backtest?result=error&message=API%20servisine%20ula%C5%9F%C4%B1lamad%C4%B1";
  try {
    const response = await fetch(`${apiBase()}/api/backtests`, {
      method: "POST",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "X-Admin-Token": process.env.ADMIN_API_TOKEN ?? "",
      },
      body: JSON.stringify(payload),
    });
    const body = (await response.json().catch(() => null)) as { id?: number; detail?: unknown } | null;
    if (response.ok && body?.id) {
      revalidatePath("/backtest");
      destination = `/backtest?run=${body.id}&result=ok&message=${encodeURIComponent("Backtest tamamlandı ve kaydedildi")}`;
    } else {
      const detail = typeof body?.detail === "string" ? body.detail : `İşlem başarısız (HTTP ${response.status})`;
      destination = `/backtest?result=error&message=${encodeURIComponent(detail)}`;
    }
  } catch {
    // Varsayilan baglanti hatasi mesaji kullanilir.
  }
  redirect(destination);
}
