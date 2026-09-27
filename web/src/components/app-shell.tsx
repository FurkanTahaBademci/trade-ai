"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Icon, type IconName } from "./icon";
import { CommandPalette } from "./command-palette";
import { ThemeToggle } from "./theme-toggle";


const nav: { label: string; href: string; icon: IconName }[] = [
  { label: "Genel Bakış", href: "/", icon: "home" },
  { label: "Piyasalar", href: "/piyasalar", icon: "markets" },
  { label: "Karşılaştır", href: "/karsilastir", icon: "activity" },
  { label: "İzleme Listesi", href: "/izleme-listesi", icon: "star" },
  { label: "Bileşik Sinyaller", href: "/sinyaller", icon: "activity" },
  { label: "Paper Portföy", href: "/portfoy", icon: "trend" },
  { label: "Backtest", href: "/backtest", icon: "activity" },
  { label: "Faiz & Makro", href: "/makro", icon: "building" },
  { label: "Haber Akışı", href: "/haberler", icon: "news" },
  { label: "KAP Bildirimleri", href: "/kap", icon: "kap" },
  { label: "AI Analizleri", href: "/analizler", icon: "ai" },
  { label: "Kurumsal Veriler", href: "/kurumsal", icon: "funds" },
  { label: "Sistem Sağlığı", href: "/sistem", icon: "activity" },
];

function Brand() {
  return <Link href="/" className="flex items-center gap-2.5" aria-label="TradeAI ana sayfa"><span className="grid h-8 w-8 place-items-center rounded bg-[var(--primary)] text-[var(--primary-contrast)]"><Icon name="trend" size={18}/></span><span className="text-[17px] font-semibold tracking-[-0.03em]">Trade<span className="text-[var(--primary)]">AI</span></span></Link>;
}

const groups = [
  { label: "01 / PİYASA", routes: ["/", "/piyasalar", "/izleme-listesi", "/karsilastir"] },
  { label: "02 / ARAŞTIRMA", routes: ["/sinyaller", "/haberler", "/kap", "/analizler", "/makro", "/kurumsal"] },
  { label: "03 / STRATEJİ", routes: ["/portfoy", "/backtest"] },
  { label: "04 / OPERASYON", routes: ["/sistem"] },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const sidebar = useRef<HTMLElement>(null);
  const title = nav.find((item) => item.href === "/" ? pathname === "/" : pathname.startsWith(item.href))?.label ?? "Piyasa Terminali";

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    sidebar.current?.querySelector<HTMLElement>("a, button")?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setOpen(false); menuButton.current?.focus(); }
      if (event.key !== "Tab") return;
      const elements = Array.from(sidebar.current?.querySelectorAll<HTMLElement>("a, button") ?? []).filter((el) => el.getClientRects().length);
      const first = elements[0], last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    const desktop = window.matchMedia("(min-width: 1024px)");
    const onResize = () => { if (desktop.matches) setOpen(false); };
    window.addEventListener("keydown", onKey);
    desktop.addEventListener("change", onResize);
    return () => { document.body.style.overflow = previousOverflow; window.removeEventListener("keydown", onKey); desktop.removeEventListener("change", onResize); };
  }, [open]);

  return <div className="min-h-screen">
    <a href="#workspace" className="fixed left-3 top-3 z-[60] -translate-y-20 rounded bg-[var(--primary)] px-4 py-2 text-[var(--primary-contrast)] focus:translate-y-0">İçeriğe geç</a>
    {open && <button className="fixed inset-0 z-40 bg-[var(--overlay)] lg:hidden" aria-label="Menüyü kapat" onClick={() => { setOpen(false); menuButton.current?.focus(); }}/>}
    <aside ref={sidebar} id="terminal-navigation" aria-label="Terminal menüsü" role={open ? "dialog" : undefined} aria-modal={open || undefined} className={`fixed inset-y-0 left-0 z-50 flex w-[208px] flex-col border-r border-[var(--border)] bg-[var(--sidebar)] lg:visible lg:translate-x-0 ${open ? "visible translate-x-0" : "invisible -translate-x-full"}`}>
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--border)] px-4"><Brand/><button className="icon-button border-0 lg:hidden" onClick={() => { setOpen(false); menuButton.current?.focus(); }} aria-label="Menüyü kapat"><Icon name="close"/></button></div>
      <nav aria-label="Ana gezinme" className="min-h-0 flex-1 overflow-y-auto px-2 py-3">{groups.map((group) => <div key={group.label} className="mb-4"><p className="terminal-mono mb-1.5 px-3 text-[10px] tracking-wider text-[var(--text-muted)]">{group.label}</p>{group.routes.map((route) => {
        const item = nav.find((entry) => entry.href === route)!;
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined} onClick={() => setOpen(false)} className={`flex min-h-9 items-center gap-2.5 border-l-2 px-3 py-2 text-xs font-medium transition-colors ${active ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary)]" : "border-transparent text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]"}`}><Icon name={item.icon} size={15}/>{item.label}</Link>;
      })}</div>)}</nav>
      <div className="shrink-0 border-t border-[var(--border)] px-4 py-3 text-[10px] leading-5 text-[var(--text-muted)]"><p className="terminal-mono text-[var(--text-secondary)]">BIST / TRY / EOD</p><p>Paper işlem · Simülasyon</p></div>
    </aside>
    <div className="min-w-0 lg:pl-[208px]">
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-[var(--border)] bg-[var(--background)] px-4 lg:px-5">
        <button ref={menuButton} className="icon-button lg:hidden" onClick={() => setOpen(true)} aria-label="Menüyü aç" aria-expanded={open} aria-controls="terminal-navigation"><Icon name="menu"/></button>
        <div className="min-w-0"><p className="truncate text-xs font-semibold">{title}</p><p className="terminal-mono hidden text-[10px] text-[var(--text-muted)] sm:block">PİYASA ARAŞTIRMA TERMİNALİ</p></div>
        <div className="ml-auto flex shrink-0 items-center gap-2"><CommandPalette/><ThemeToggle/></div>
      </header>
      <main id="workspace" tabIndex={-1} className="mx-auto min-w-0 max-w-[1760px] p-3 sm:p-4 lg:p-5">{children}</main>
    </div>
  </div>;
}
