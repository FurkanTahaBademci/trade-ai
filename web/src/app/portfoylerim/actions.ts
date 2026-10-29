"use server";

import { redirect } from "next/navigation";
import type { FormState } from "@/app/giris/actions";
import { accountRequest, sessionToken } from "@/lib/account-server";
import { parseAmount, parseStrategyConfig } from "@/lib/paper-forms";
import type { MyPortfolio, PaperOrder } from "@/lib/types";

async function requireToken(next: string): Promise<string> {
  const token = await sessionToken();
  if (!token) redirect(`/giris?next=${encodeURIComponent(next)}`);
  return token;
}

function portfolioId(formData: FormData): number {
  const id = Number(formData.get("portfolio_id"));
  if (!Number.isInteger(id) || id <= 0) redirect("/portfoylerim");
  return id;
}

function finish(id: number, result: { ok: boolean; message: string }): never {
  redirect(`/portfoylerim/${id}?result=${result.ok ? "ok" : "error"}&message=${encodeURIComponent(result.message)}`);
}

export async function createPortfolioAction(_previous: FormState, formData: FormData): Promise<FormState> {
  const token = await requireToken("/portfoylerim/yeni");
  const kind = formData.get("kind") === "MANUAL" ? "MANUAL" : "STRATEGY";
  const values = { name: String(formData.get("name") ?? "").trim() };
  const body: Record<string, unknown> = { name: values.name, kind, initial_cash: Number(formData.get("initial_cash")) };
  if (kind === "STRATEGY") {
    const parsed = parseStrategyConfig((name) => formData.get(name));
    if ("error" in parsed) return { message: parsed.error, values };
    body.config = parsed.config;
  }
  const result = await accountRequest<MyPortfolio>("/api/me/portfolios", token, { body });
  if (!result.ok) return { message: result.message, code: result.code, values };
  redirect(`/portfoylerim/${result.data.id}?result=ok&message=${encodeURIComponent("Portföy oluşturuldu.")}`);
}

export async function updatePortfolioAction(formData: FormData) {
  const id = portfolioId(formData);
  const token = await requireToken(`/portfoylerim/${id}`);
  const body: Record<string, unknown> = {};
  const name = formData.get("name");
  if (typeof name === "string") body.name = name.trim();
  const status = formData.get("status");
  if (status === "ACTIVE" || status === "PAUSED") body.status = status;
  if (formData.get("has_config") === "1") {
    const parsed = parseStrategyConfig((key) => formData.get(key));
    if ("error" in parsed) finish(id, { ok: false, message: parsed.error });
    body.config = parsed.config;
  }
  const result = await accountRequest(`/api/me/portfolios/${id}`, token, { method: "PATCH", body });
  const message = status === "PAUSED" ? "Portföy duraklatıldı; işlem yapılmaz, değerleme sürer." : status === "ACTIVE" ? "Portföy yeniden etkin." : body.config ? "Strateji ayarları kaydedildi; bir sonraki işlem gününden itibaren geçerli." : "Portföy güncellendi.";
  finish(id, result.ok ? { ok: true, message } : result);
}

export async function deletePortfolioAction(formData: FormData) {
  const id = portfolioId(formData);
  const token = await requireToken(`/portfoylerim/${id}`);
  if (formData.get("confirm") !== "on") finish(id, { ok: false, message: "Silmeyi onaylamak için kutuyu işaretle." });
  const result = await accountRequest(`/api/me/portfolios/${id}`, token, { method: "DELETE" });
  if (!result.ok) finish(id, result);
  redirect(`/portfoylerim?result=ok&message=${encodeURIComponent("Portföy ve tüm işlemleri silindi.")}`);
}

export async function placeOrderAction(_previous: FormState, formData: FormData): Promise<FormState> {
  const id = portfolioId(formData);
  const token = await requireToken(`/portfoylerim/${id}`);
  const ticker = String(formData.get("ticker") ?? "").trim().toLocaleUpperCase("tr-TR");
  const side = formData.get("side") === "SELL" ? "SELL" : "BUY";
  const mode = side === "SELL" ? "quantity" : formData.get("mode") === "amount" ? "amount" : "quantity";
  const size = parseAmount(formData.get("size"));
  const values = { ticker, size: String(formData.get("size") ?? "") };
  if (!ticker) return { message: "Hisse kodunu gir.", values };
  if (size == null) return { message: mode === "amount" ? "Geçerli bir TL tutarı gir." : "Geçerli bir adet gir.", values };
  if (mode === "quantity" && !Number.isInteger(size)) return { message: "Adet tam sayı olmalı.", values };
  const result = await accountRequest<PaperOrder>(`/api/me/portfolios/${id}/orders`, token, {
    body: { ticker, side, [mode]: size, client_order_id: String(formData.get("client_order_id") ?? "") || undefined },
  });
  if (!result.ok) return { message: result.message, code: result.code, values };
  const day = new Intl.DateTimeFormat("tr-TR", { day: "2-digit", month: "long", weekday: "long" }).format(new Date(`${result.data.not_before}T12:00:00`));
  finish(id, { ok: true, message: `${ticker} ${side === "BUY" ? "alış" : "satış"} emri alındı; ${day} kapanış fiyatından gerçekleşecek.` });
}

export async function cancelOrderAction(formData: FormData) {
  const id = portfolioId(formData);
  const token = await requireToken(`/portfoylerim/${id}`);
  const orderId = Number(formData.get("order_id"));
  const result = await accountRequest(`/api/me/portfolios/${id}/orders/${orderId}`, token, { method: "DELETE" });
  finish(id, result.ok ? { ok: true, message: "Emir iptal edildi." } : result);
}
