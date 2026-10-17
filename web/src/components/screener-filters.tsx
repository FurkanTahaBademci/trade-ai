"use client";

import { useId, useState } from "react";
import { Icon } from "./icon";

/**
 * Tarayıcı filtre formu kabı. Masaüstünde form hep açıktır; mobilde 11 alan
 * sonuçları ekranın çok altına ittiği için "Filtreler" düğmesiyle açılır.
 * Kapalı hâl CSS kırılımıyla çizilir (sunucu HTML'i ile hidrasyon aynı kalır).
 */
export function ScreenerFilters({ activeCount, children }: { activeCount: number; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return <div className="mb-5">
    <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} aria-controls={id} className="panel-flat flex w-full items-center justify-between gap-3 px-4 py-3 text-sm font-semibold md:hidden">
      <span className="flex items-center gap-2">
        <Icon name="search" size={15} className="text-[var(--text-muted)]"/>
        Filtreler
        {activeCount > 0 && <span className="pill pill-primary" aria-label={`${activeCount} aktif filtre`}>{activeCount}</span>}
      </span>
      <Icon name="chevron" size={16} className={`text-[var(--text-muted)] transition-transform ${open ? "-rotate-90" : "rotate-90"}`}/>
    </button>
    <div id={id} className={`${open ? "mt-2 block" : "hidden"} md:mt-0 md:block`}>{children}</div>
  </div>;
}
