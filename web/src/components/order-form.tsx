"use client";

import { useActionState, useEffect, useState } from "react";
import { placeOrderAction } from "@/app/portfoylerim/actions";
import type { FormState } from "@/app/giris/actions";
import { FormMessage } from "./account-forms";

type PortfolioOption = { id: number; name: string; cash: number };

/** Manuel portföye sanal alış/satış emri. Portföy listesi verilirse seçim kutusu çıkar. */
export function OrderForm({ portfolios, ticker = "" }: { portfolios: PortfolioOption[]; ticker?: string }) {
  const [state, action, pending] = useActionState(placeOrderAction, {} as FormState);
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [mode, setMode] = useState<"amount" | "quantity">("amount");
  // Aynı formun iki kez gönderilmesi tek emir açar (API client_order_id ile eşler).
  // Kimlik yalnız tarayıcıda üretilir; sunucu render'ıyla farklı değer hydration hatası verir.
  const [clientOrderId, setClientOrderId] = useState("");
  useEffect(() => { setClientOrderId(typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`); }, []);
  const effectiveMode = side === "SELL" ? "quantity" : mode;
  const label = "mb-1.5 block text-[11px] font-medium text-[var(--text-muted)]";

  return <form action={action} aria-busy={pending} className="space-y-4">
    <input type="hidden" name="client_order_id" value={clientOrderId}/>
    <input type="hidden" name="side" value={side}/>
    <input type="hidden" name="mode" value={effectiveMode}/>
    <fieldset disabled={pending} className="space-y-4 disabled:opacity-60">
      {portfolios.length > 1
        ? <label className="block"><span className={label}>Portföy</span><select className="input" name="portfolio_id" defaultValue={portfolios[0].id}>{portfolios.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.cash.toLocaleString("tr-TR", { maximumFractionDigits: 0 })} TL nakit</option>)}</select></label>
        : <input type="hidden" name="portfolio_id" value={portfolios[0]?.id ?? ""}/>}
      <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Emir yönü">
        {(["BUY", "SELL"] as const).map((value) => <button key={value} type="button" role="radio" aria-checked={side === value} onClick={() => setSide(value)} className={`h-10 rounded border text-sm font-semibold transition ${side === value ? (value === "BUY" ? "border-[var(--positive)] bg-[var(--positive-soft)] text-[var(--positive)]" : "border-[var(--negative)] bg-[var(--negative-soft)] text-[var(--negative)]") : "border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text)]"}`}>{value === "BUY" ? "Al" : "Sat"}</button>)}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block"><span className={label}>Hisse kodu</span><input className="input uppercase" name="ticker" required maxLength={16} autoComplete="off" autoCapitalize="characters" spellCheck={false} placeholder="THYAO" defaultValue={state.values?.ticker ?? ticker}/></label>
        <label className="block">
          <span className="mb-1.5 flex items-center justify-between text-[11px] font-medium text-[var(--text-muted)]"><span>{effectiveMode === "amount" ? "Tutar (TL)" : "Adet"}</span>{side === "BUY" && <button type="button" onClick={() => setMode(mode === "amount" ? "quantity" : "amount")} className="text-[var(--primary)]">{mode === "amount" ? "Adetle gir" : "Tutarla gir"}</button>}</span>
          <input className="input" name="size" required inputMode="decimal" autoComplete="off" placeholder={effectiveMode === "amount" ? "10.000" : "100"} defaultValue={state.values?.size ?? ""}/>
        </label>
      </div>
    </fieldset>
    <FormMessage state={state}/>
    <button disabled={pending || !portfolios.length} className="h-11 w-full rounded bg-[var(--primary)] px-4 text-sm font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)] disabled:cursor-wait disabled:opacity-60">{pending ? "Gönderiliyor…" : side === "BUY" ? "Alış emri ver" : "Satış emri ver"}</button>
    <p className="text-[10px] leading-4 text-[var(--text-muted)]">Emir gerçek değildir. 18:00'den önce verilen emir o günün, sonra verilen emir bir sonraki işlem gününün kapanış fiyatından %0,05 kayma ve %0,1 komisyonla gerçekleşir. Tavan/tabanda kapanan ya da işlem görmeyen hissede emir bekler; 7 gün içinde gerçekleşmezse reddedilir.</p>
  </form>;
}
