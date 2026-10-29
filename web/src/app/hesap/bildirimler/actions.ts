"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { accountRequest, sessionToken } from "@/lib/account-server";
import type { AlertPrefs } from "@/lib/types";

const PAGE = "/hesap/bildirimler";

/** Telegram bağlama panelinin durumu (useActionState). */
export type TelegramLinkState = { url?: string; expiresAt?: string; message?: string; ok?: boolean };

async function requireToken(): Promise<string> {
  const token = await sessionToken();
  if (!token) redirect(`/giris?next=${PAGE}`);
  return token;
}

function finish(result: { ok: boolean; message: string }): never {
  redirect(`${PAGE}?result=${result.ok ? "ok" : "error"}&message=${encodeURIComponent(result.message)}`);
}

export async function savePreferencesAction(formData: FormData) {
  const token = await requireToken();
  const result = await accountRequest<AlertPrefs>("/api/me/alerts", token, {
    method: "PUT",
    body: {
      telegram_instant: formData.get("telegram_instant") === "on",
      telegram_digest: formData.get("telegram_digest") === "on",
      email_digest: formData.get("email_digest") === "on",
    },
  });
  finish(result.ok ? { ok: true, message: "Bildirim tercihlerin kaydedildi." } : result);
}

export async function createTelegramLinkAction(_previous: TelegramLinkState): Promise<TelegramLinkState> {
  const token = await requireToken();
  const result = await accountRequest<{ url: string; expires_at: string }>("/api/me/alerts/telegram/link", token, { method: "POST" });
  if (!result.ok) return { message: result.message };
  return { url: result.data.url, expiresAt: result.data.expires_at };
}

/** Bot'a gelen mesajları hemen işletir; bağlandıysa sayfa bağlı durumla yeniden çizilir. */
export async function checkTelegramAction(previous: TelegramLinkState): Promise<TelegramLinkState> {
  const token = await requireToken();
  const result = await accountRequest<AlertPrefs>("/api/me/alerts/telegram/check", token, { method: "POST" });
  if (!result.ok) return { ...previous, ok: false, message: result.message };
  if (result.data.telegram_linked) {
    revalidatePath(PAGE);
    return { ok: true, message: "Telegram bağlandı." };
  }
  return { ...previous, ok: false, message: "Henüz bağlantı görünmüyor. Telegram'da bot'u açıp “Başlat”a bastığından emin ol, birkaç saniye sonra yeniden dene." };
}

export async function unlinkTelegramAction() {
  const token = await requireToken();
  const result = await accountRequest("/api/me/alerts/telegram", token, { method: "DELETE" });
  finish(result.ok ? { ok: true, message: "Telegram bağlantısı kaldırıldı." } : result);
}

export async function sendTestMessageAction() {
  const token = await requireToken();
  const result = await accountRequest<{ message: string }>("/api/me/alerts/test", token, { method: "POST" });
  finish(result.ok ? { ok: true, message: result.data.message } : result);
}
