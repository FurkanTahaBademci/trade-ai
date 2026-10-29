"use client";

import { useActionState, useState } from "react";
import { createPortfolioAction } from "@/app/portfoylerim/actions";
import type { FormState } from "@/app/giris/actions";
import type { StrategyTemplate } from "@/lib/types";
import { FormMessage } from "./account-forms";
import { StrategyConfigFields } from "./strategy-config-fields";

const CASH_OPTIONS = [100_000, 250_000, 1_000_000, 5_000_000, 10_000_000];

export function NewPortfolioForm({ templates, initialKind }: { templates: StrategyTemplate[]; initialKind: "STRATEGY" | "MANUAL" }) {
  const [state, action, pending] = useActionState(createPortfolioAction, {} as FormState);
  const [kind, setKind] = useState(initialKind);
  const [templateKey, setTemplateKey] = useState(templates[0]?.key ?? "model");
  const template = templates.find((item) => item.key === templateKey) ?? templates[0];

  return <form action={action} aria-busy={pending} className="space-y-6">
    <fieldset disabled={pending} className="space-y-6 disabled:opacity-60">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block"><span className="mb-1.5 block text-[11px] font-medium text-[var(--text-muted)]">Portföy adı</span><input className="input" name="name" maxLength={64} required placeholder="ör. Temkinli deneme" defaultValue={state.values?.name ?? ""} autoComplete="off"/></label>
        <label className="block"><span className="mb-1.5 block text-[11px] font-medium text-[var(--text-muted)]">Başlangıç bakiyesi (sanal)</span><select className="input" name="initial_cash" defaultValue={1_000_000}>{CASH_OPTIONS.map((value) => <option key={value} value={value}>{value.toLocaleString("tr-TR")} TL</option>)}</select></label>
      </div>

      <div role="radiogroup" aria-label="Portföy türü" className="grid gap-3 sm:grid-cols-2">
        {([["STRATEGY", "Strateji portföyü", "Bileşik sinyali seçtiğin kurallarla her işlem günü otomatik izler; alım-satımı motor yapar."], ["MANUAL", "Manuel portföy", "Alım-satım emirlerini sen verirsin; emirler gün sonu kapanış fiyatından gerçekleşir."]] as const).map(([value, label, description]) => <label key={value} className={`panel-flat cursor-pointer p-4 transition ${kind === value ? "ring-2 ring-[var(--primary)]" : "hover:bg-[var(--surface-hover)]"}`}>
          <span className="flex items-center gap-2 text-sm font-semibold"><input type="radio" name="kind" value={value} checked={kind === value} onChange={() => setKind(value)}/>{label}</span>
          <span className="mt-1.5 block text-xs leading-5 text-[var(--text-secondary)]">{description}</span>
        </label>)}
      </div>

      {kind === "STRATEGY" && template && <section className="space-y-4">
        <div>
          <p className="mb-2 text-[11px] font-medium text-[var(--text-muted)]">Hazır şablon</p>
          <div className="grid gap-3 md:grid-cols-3">{templates.map((item) => <button type="button" key={item.key} onClick={() => setTemplateKey(item.key)} aria-pressed={item.key === templateKey} className={`panel-flat p-3 text-left transition ${item.key === templateKey ? "ring-2 ring-[var(--primary)]" : "hover:bg-[var(--surface-hover)]"}`}><span className="text-sm font-semibold">{item.label}</span><span className="mt-1 block text-[11px] leading-4 text-[var(--text-secondary)]">{item.description}</span></button>)}</div>
        </div>
        <details className="panel-flat p-4"><summary className="cursor-pointer text-xs font-semibold">Ayarları incele ve değiştir</summary><div className="mt-4"><StrategyConfigFields key={template.key} config={template.config}/></div></details>
      </section>}
    </fieldset>
    <FormMessage state={state}/>
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <button disabled={pending} className="h-11 rounded bg-[var(--primary)] px-6 text-sm font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)] disabled:cursor-wait disabled:opacity-60">{pending ? "Oluşturuluyor…" : "Portföyü oluştur"}</button>
      <p className="text-[11px] leading-5 text-[var(--text-muted)]">İlk işlemler, saat 18:00'den önce oluşturulursa bugünkü, sonra oluşturulursa bir sonraki işlem gününün kapanışında yapılır. Geçmiş günler oynatılmaz.</p>
    </div>
  </form>;
}
