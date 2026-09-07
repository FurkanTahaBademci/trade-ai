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
    if (response.ok) return { ok: true, message: "Takvim güncellendi" };
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
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
