"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

function apiBase() {
  return process.env.API_INTERNAL_URL ?? "http://localhost:8000";
}

async function mutate(path: string, init: RequestInit): Promise<{ ok: boolean; message: string }> {
  try {
    const response = await fetch(`${apiBase()}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "X-Admin-Token": process.env.ADMIN_API_TOKEN ?? "",
        ...init.headers,
      },
    });
    const payload = (await response.json().catch(() => null)) as { detail?: string; message?: string } | null;
    if (response.ok) return { ok: true, message: payload?.message ?? "İşlem tamamlandı" };
    return { ok: false, message: payload?.detail ?? `İşlem başarısız (HTTP ${response.status})` };
  } catch {
    return { ok: false, message: "API servisine ulaşılamadı" };
  }
}

function finish(result: { ok: boolean; message: string }) {
  revalidatePath("/sistem");
  redirect(`/sistem?result=${result.ok ? "ok" : "error"}&message=${encodeURIComponent(result.message)}`);
}

export async function updateScheduleAction(formData: FormData) {
  const name = String(formData.get("name") ?? "");
  const interval = Number(formData.get("interval_minutes"));
  const result = await mutate(`/api/schedules/${encodeURIComponent(name)}`, {
    method: "PATCH",
    body: JSON.stringify({ interval_minutes: interval }),
  });
  finish(result);
}

export async function toggleScheduleAction(formData: FormData) {
  const name = String(formData.get("name") ?? "");
  const enabled = String(formData.get("enabled")) === "true";
  const result = await mutate(`/api/schedules/${encodeURIComponent(name)}`, {
    method: "PATCH",
    body: JSON.stringify({ enabled }),
  });
  finish({ ...result, message: result.ok ? (enabled ? "Takvim etkinleştirildi" : "Takvim duraklatıldı") : result.message });
}

export async function runScheduleAction(formData: FormData) {
  const name = String(formData.get("name") ?? "");
  const result = await mutate(`/api/schedules/${encodeURIComponent(name)}/run`, {
    method: "POST",
  });
  finish({ ...result, message: result.ok ? "İş Redis kuyruğuna eklendi" : result.message });
}

export async function updateSettingAction(formData: FormData) {
  const key = String(formData.get("key") ?? "");
  const value = String(formData.get("value") ?? "").trim();
  const result = await mutate(`/api/settings/${encodeURIComponent(key)}`, {
    method: "PUT",
    body: JSON.stringify({ value }),
  });
  finish({ ...result, message: result.ok ? "Ayar güncellendi" : result.message });
}

export async function clearSettingAction(formData: FormData) {
  const key = String(formData.get("key") ?? "");
  const result = await mutate(`/api/settings/${encodeURIComponent(key)}`, { method: "DELETE" });
  finish({ ...result, message: result.ok ? "Ayar .env varsayılanına döndürüldü" : result.message });
}

export async function testGeminiAction(formData: FormData) {
  const tier = Number(formData.get("tier"));
  if (tier !== 1 && tier !== 2) {
    finish({ ok: false, message: "Geçersiz Gemini katmanı" });
  }
  const result = await mutate("/api/settings/gemini/test", {
    method: "POST",
    body: JSON.stringify({ tier }),
  });
  finish({
    ...result,
    message: result.ok ? `Tier ${tier} bağlantısı başarılı: ${result.message}` : result.message,
  });
}

export async function vacuumStorageAction() {
  const result = await mutate("/api/system/storage/vacuum", {
    method: "POST",
  });
  finish({
    ...result,
    message: result.ok ? (result.message || "Depolama vakumlandı ve disk alanı temizlendi") : result.message,
  });
}

