"use client";

import { useActionState } from "react";
import { createBacktestAction } from "@/app/backtest/actions";
import { backtestFields, type BacktestField, type BacktestFormState } from "@/lib/backtest-form";

export function BacktestForm({ startDate, endDate }: { startDate: string; endDate: string }) {
  const initial = { values: { ...Object.fromEntries(Object.entries(backtestFields).map(([name, field]) => [name, field.value])), start_date: startDate, end_date: endDate } } as BacktestFormState;
  const [state, action, pending] = useActionState(createBacktestAction, initial);
  return <form action={action} aria-busy={pending} className="space-y-4">
    <fieldset disabled={pending} className="grid min-w-0 grid-cols-2 gap-3 disabled:opacity-60">
      {(Object.keys(backtestFields) as BacktestField[]).map((name) => {
        const field = backtestFields[name];
        return <label key={name} className={`block min-w-0 ${name === "initial_cash" ? "col-span-2" : ""}`}>
          <span className="mb-1.5 block text-[11px] font-medium text-[var(--text-muted)]">{field.label}</span>
          <input className="input min-w-0" name={name} type={field.type} required defaultValue={state.values[name]}
            {...("min" in field ? { min: field.min, max: field.max, step: field.step } : {})}
            aria-invalid={!!state.errors?.[name]} aria-describedby={state.errors?.[name] ? `${name}-error` : undefined}/>
          {state.errors?.[name] && <span id={`${name}-error`} className="mt-1 block text-xs text-[var(--negative)]">{state.errors[name]}</span>}
        </label>;
      })}
    </fieldset>
    {state.message && <p role="alert" className="text-xs text-[var(--negative)]">{state.message}</p>}
    <button disabled={pending} className="h-11 w-full rounded bg-[var(--primary)] px-4 text-sm font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)] disabled:cursor-wait disabled:opacity-60">{pending ? "Hesaplanıyor…" : "Backtest çalıştır"}</button>
    <p role="status" className="text-xs leading-5 text-[var(--text-muted)]">{pending ? "Seçilen dönemin sinyal ve fiyatları değerlendiriliyor." : "Pozisyon sayısı × ağırlık en fazla %100 olabilir."}</p>
  </form>;
}
