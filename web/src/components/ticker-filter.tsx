import Link from "next/link";
import { normalizeTicker } from "@/lib/turkish";
import { Icon } from "./icon";

/** `?hisse=` parametresi: geçerli bir BIST kodu değilse yok sayılır. */
export function tickerParam(raw: string | string[] | undefined) {
  const value = normalizeTicker(Array.isArray(raw) ? raw[0] ?? "" : raw ?? "");
  return /^[A-Z0-9]{2,8}$/.test(value) ? value : undefined;
}

/** Liste sayfalarında hisse koduna göre filtre; diğer parametreler gizli alanla korunur. */
export function TickerFilter({ action, ticker, keep = {} }: { action: string; ticker?: string; keep?: Record<string, string | undefined> }) {
  const clear = new URLSearchParams(Object.entries(keep).filter((entry): entry is [string, string] => Boolean(entry[1]))).toString();
  return <form action={action} method="get" className="mb-4 flex flex-wrap items-center gap-2" role="search">
    {Object.entries(keep).map(([name, value]) => value ? <input key={name} type="hidden" name={name} value={value}/> : null)}
    <label className="relative"><span className="sr-only">Hisse kodu</span><Icon name="search" size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"/><input name="hisse" defaultValue={ticker ?? ""} placeholder="Hisse kodu (ör. THYAO)" autoComplete="off" className="input h-9 w-52 pl-8 text-xs uppercase"/></label>
    <button type="submit" className="pill h-9 transition hover:text-[var(--text)]">Filtrele</button>
    {ticker && <><Link prefetch={false} href={`/piyasalar/${ticker}`} className="pill pill-primary h-9">{ticker} sayfası</Link><Link prefetch={false} href={clear ? `${action}?${clear}` : action} className="pill h-9 transition hover:text-[var(--text)]" aria-label={`${ticker} filtresini kaldır`}>Filtreyi kaldır <Icon name="close" size={12}/></Link></>}
  </form>;
}
