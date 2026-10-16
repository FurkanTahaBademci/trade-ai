"use client";

import { useActionState, useState } from "react";
import { createBacktestAction } from "@/app/backtest/actions";
import { backtestFields, fieldGroups, type BacktestField, type BacktestFormState } from "@/lib/backtest-form";

export function BacktestForm({ startDate, endDate }: { startDate: string; endDate: string }) {
  const initial = { values: { ...Object.fromEntries(Object.entries(backtestFields).map(([name, field]) => [name, field.value])), start_date: startDate, end_date: endDate } } as BacktestFormState;
  const [state, action, pending] = useActionState(createBacktestAction, initial);
  const [strategy, setStrategy] = useState(state.values.strategy);
  // Seçili stratejide kullanılmayan grup kapalı gösterilir (değerleri yine gönderilir).
  const inactive = strategy === "basket" ? "threshold" : "basket";
  return <form action={action} aria-busy={pending} className="space-y-4">
    {fieldGroups.map((group) => {
      const names = (Object.keys(backtestFields) as BacktestField[]).filter((name) => backtestFields[name].group === group.key);
      const collapsed = group.key === inactive || group.key === "weights";
      return <details key={group.key} open={!collapsed} className="group/fs">
        <summary className="mb-2 cursor-pointer select-none text-xs font-semibold text-[var(--text)]">{group.title}{group.key === inactive && <span className="ml-1.5 font-normal text-[var(--text-muted)]">· bu stratejide kullanılmaz</span>}</summary>
        {group.hint && <p className="mb-2 text-[11px] leading-4 text-[var(--text-muted)]">{group.hint}</p>}
        <fieldset disabled={pending} className="grid min-w-0 grid-cols-2 gap-3 disabled:opacity-60">
          {names.map((name) => <FormField key={name} name={name} state={state} onStrategy={setStrategy}/>)}
        </fieldset>
      </details>;
    })}
    {state.message && <p role="alert" className="text-xs text-[var(--negative)]">{state.message}</p>}
    <button disabled={pending} className="h-11 w-full rounded bg-[var(--primary)] px-4 text-sm font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)] disabled:cursor-wait disabled:opacity-60">{pending ? "Hesaplanıyor…" : "Backtest çalıştır"}</button>
    <p role="status" className="text-xs leading-5 text-[var(--text-muted)]">{pending ? "Seçilen dönemin sinyal ve fiyatları değerlendiriliyor; sonuç ayrıca 4 kaydırılmış başlangıçla tekrarlanır." : "Sonuç, başlangıcı 2–8 işlem günü kaydırılmış 4 ek koşuyla birlikte raporlanır."}</p>
  </form>;
}

function FormField({ name, state, onStrategy }: { name: BacktestField; state: BacktestFormState; onStrategy: (value: string) => void }) {
  const field = backtestFields[name];
  const error = state.errors?.[name];
  const common = { name, required: true, defaultValue: state.values[name], "aria-invalid": !!error, "aria-describedby": error ? `${name}-error` : undefined };
  return <label className={`block min-w-0 ${name === "initial_cash" || name === "strategy" ? "col-span-2" : ""}`}>
    <span className="mb-1.5 block text-[11px] font-medium text-[var(--text-muted)]">{field.label}</span>
    {field.type === "select"
      ? <select className="input min-w-0" {...common} onChange={(event) => onStrategy(event.target.value)}>{field.options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
      : <input className="input min-w-0" type={field.type} {...common} {...(field.type === "number" ? { min: field.min, max: field.max, step: field.step } : {})}/>}
    {error && <span id={`${name}-error`} className="mt-1 block text-xs text-[var(--negative)]">{error}</span>}
  </label>;
}
