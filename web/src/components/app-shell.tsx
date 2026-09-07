"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Icon, type IconName } from "./icon";

const nav: { label: string; href: string; icon: IconName }[] = [
  { label: "Genel Bakış", href: "/", icon: "home" },
  { label: "Piyasalar", href: "/piyasalar", icon: "markets" },
  { label: "Haber Akışı", href: "/haberler", icon: "news" },
  { label: "KAP Bildirimleri", href: "/kap", icon: "kap" },
  { label: "AI Analizleri", href: "/analizler", icon: "ai" },
  { label: "Kurumsal Veriler", href: "/kurumsal", icon: "funds" },
];

function Brand() {
  return <Link href="/" className="flex items-center gap-2.5" aria-label="TradeAI ana sayfa"><span className="grid h-8 w-8 place-items-center rounded-[9px] bg-[var(--primary)] text-[var(--primary-contrast)]"><Icon name="trend" size={18}/></span><span className="text-[17px] font-semibold tracking-[-0.03em]">Trade<span className="text-[var(--primary)]">AI</span></span></Link>;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const title = nav.find((item) => item.href === "/" ? pathname === "/" : pathname.startsWith(item.href))?.label ?? "Piyasa Terminali";

  return <div className="min-h-screen">
    {open && <button className="fixed inset-0 z-40 bg-[var(--overlay)] lg:hidden" aria-label="Menüyü kapat" onClick={() => setOpen(false)}/>} 
    <aside className={`fixed inset-y-0 left-0 z-50 flex w-[248px] flex-col border-r bg-[var(--sidebar)] transition-transform lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`} style={{ borderColor: "var(--border)" }}>
      <div className="flex h-[72px] items-center justify-between px-5"><Brand/><button className="icon-button border-0 lg:hidden" onClick={() => setOpen(false)} aria-label="Menüyü kapat"><Icon name="close"/></button></div>
      <nav className="flex-1 px-3 pt-4"><p className="eyebrow mb-3 px-3">Terminal</p><div className="space-y-1">{nav.map((item) => {
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return <Link key={item.href} href={item.href} onClick={() => setOpen(false)} className={`flex items-center gap-3 rounded-[10px] px-3 py-2.5 text-sm font-medium transition ${active ? "bg-[var(--primary-soft)] text-[var(--primary)]" : "text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]"}`}><Icon name={item.icon} size={18}/>{item.label}{active && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[var(--primary)]"/>}</Link>;
      })}</div></nav>
      <div className="m-4 rounded-[12px] border p-3.5" style={{ borderColor: "var(--border)", background: "var(--surface)" }}><div className="mb-2 flex items-center gap-2 text-xs font-medium"><span className="h-2 w-2 rounded-full bg-[var(--positive)] shadow-[0_0_0_4px_var(--positive-soft)]"/> Veri terminali</div><p className="text-[11px] leading-5 text-[var(--text-muted)]">BIST piyasa istihbaratı<br/>Paper trade • Canlı emir yok</p></div>
      <div className="border-t px-5 py-4 text-[11px] text-[var(--text-muted)]" style={{ borderColor: "var(--border)" }}>© 2026 TradeAI</div>
    </aside>

    <div className="lg:pl-[248px]">
      <header className="sticky top-0 z-30 flex h-[72px] items-center gap-3 border-b px-4 backdrop-blur-xl sm:px-6 lg:px-8" style={{ borderColor: "var(--border)", background: "color-mix(in srgb, var(--background) 88%, transparent)" }}>
        <button className="icon-button lg:hidden" onClick={() => setOpen(true)} aria-label="Menüyü aç"><Icon name="menu"/></button>
        <div><p className="text-sm font-semibold tracking-[-0.015em]">{title}</p><p className="hidden text-[11px] text-[var(--text-muted)] sm:block">BIST piyasa istihbaratı</p></div>
        <div className="ml-auto flex items-center gap-2"><Link href="/piyasalar" className="hidden h-9 w-56 items-center gap-2 rounded-[10px] border px-3 text-xs text-[var(--text-muted)] md:flex" style={{ borderColor: "var(--border)", background: "var(--surface)" }}><Icon name="search" size={15}/> Hisse ara... <kbd className="ml-auto text-[10px]">⌘ K</kbd></Link><button className="icon-button relative" aria-label="Bildirimler"><Icon name="bell" size={17}/><span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-[var(--primary)]"/></button><div className="ml-1 grid h-9 w-9 place-items-center rounded-[10px] bg-[var(--surface-raised)] text-xs font-semibold text-[var(--primary)]">FT</div></div>
      </header>
      <main className="mx-auto max-w-[1480px] p-4 sm:p-6 lg:p-8">{children}</main>
    </div>
  </div>;
}
