"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { accountRequest, clearSessionCookie, sessionToken } from "@/lib/account-server";

async function requireToken(): Promise<string> {
  const token = await sessionToken();
  if (!token) redirect("/giris?next=/hesap");
  return token;
}

function finish(result: { ok: boolean; message: string }): never {
  redirect(`/hesap?result=${result.ok ? "ok" : "error"}&message=${encodeURIComponent(result.message)}`);
}

export async function updateProfileAction(formData: FormData) {
  const token = await requireToken();
  const result = await accountRequest("/api/me", token, { method: "PATCH", body: { display_name: String(formData.get("display_name") ?? "").trim() } });
  // Üst menüdeki ad kök layout'ta; yalnız sayfa değil layout da yenilensin.
  if (result.ok) revalidatePath("/", "layout");
  finish(result.ok ? { ok: true, message: "Profil güncellendi." } : result);
}

export async function changePasswordAction(formData: FormData) {
  const token = await requireToken();
  const next = String(formData.get("new_password") ?? "");
  if (next !== String(formData.get("new_password_confirm") ?? "")) finish({ ok: false, message: "Yeni parolalar eşleşmiyor." });
  const result = await accountRequest<{ message: string }>("/api/me/password", token, { body: { current_password: String(formData.get("current_password") ?? ""), new_password: next } });
  finish(result.ok ? { ok: true, message: result.data.message } : result);
}

export async function revokeSessionAction(formData: FormData) {
  const token = await requireToken();
  const id = Number(formData.get("session_id"));
  if (!Number.isInteger(id) || id <= 0) finish({ ok: false, message: "Geçersiz oturum." });
  const result = await accountRequest(`/api/me/sessions/${id}`, token, { method: "DELETE" });
  finish(result.ok ? { ok: true, message: "Oturum kapatıldı." } : result);
}

export async function revokeOtherSessionsAction() {
  const token = await requireToken();
  const result = await accountRequest<{ message: string }>("/api/me/sessions/revoke-others", token, { method: "POST" });
  finish(result.ok ? { ok: true, message: result.data.message } : result);
}

export async function deleteAccountAction(formData: FormData) {
  const token = await requireToken();
  if (formData.get("confirm") !== "on") finish({ ok: false, message: "Silmeyi onaylamak için kutuyu işaretle." });
  const result = await accountRequest("/api/me/delete", token, { body: { password: String(formData.get("password") ?? "") } });
  if (!result.ok) finish(result);
  await clearSessionCookie();
  redirect("/giris?silindi=1");
}
