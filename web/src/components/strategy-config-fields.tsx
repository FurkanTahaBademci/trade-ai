import { STRATEGY_FIELDS } from "@/lib/paper-forms";
import type { StrategyConfig } from "@/lib/types";

/** Strateji eşikleri ve risk kuralları; oluşturma ve düzenleme formlarında ortak. */
export function StrategyConfigFields({ config }: { config: StrategyConfig }) {
  return <div className="space-y-4">
    <div className="grid gap-3 sm:grid-cols-2">
      {STRATEGY_FIELDS.map((field) => <label key={field.key} className="block">
        <span className="mb-1 block text-[11px] font-medium text-[var(--text-muted)]">{field.label}</span>
        <input className="input" type="number" name={`cfg_${field.key}`} min={field.min} max={field.max} step={field.step} defaultValue={config[field.key]} required/>
        <span className="mt-1 block text-[10px] leading-4 text-[var(--text-muted)]">{field.hint}</span>
      </label>)}
    </div>
    <label className="flex items-start gap-2 text-xs leading-5 text-[var(--text-secondary)]">
      <input type="checkbox" name="cfg_rebalance_enabled" defaultChecked={config.rebalance_enabled} className="mt-1"/>
      <span>Yeniden dengeleme: fiyat artışıyla tek pozisyon tavanının %25 üstüne çıkan pozisyonu tavana kadar kırp.</span>
    </label>
    <p className="text-[10px] leading-4 text-[var(--text-muted)]">Komisyon (%0,1), fiyat kayması (%0,05), tavan/tabanda işlem yapılmaması ve günlük 20 milyon TL altı ortalama hacimli hisselere girilmemesi herkes için aynıdır.</p>
  </div>;
}
