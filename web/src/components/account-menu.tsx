"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { type AccountSummary, accountInitials } from "@/lib/account";
import { LogoutForm } from "./logout-form";

const itemClass = "flex min-h-9 w-full items-center rounded px-3 text-left text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text)]";

export function AccountMenu({ account }: { account: AccountSummary | null }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => { if (!container.current?.contains(event.target as Node)) setOpen(false); };
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpen(false); button.current?.focus(); } };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("pointerdown", onPointer); document.removeEventListener("keydown", onKey); };
  }, [open]);

  if (!account) {
    const next = pathname && pathname !== "/" && !pathname.startsWith("/giris") ? `?next=${encodeURIComponent(pathname)}` : "";
    return <div className="flex items-center gap-1.5">
      <Link prefetch={false} href={`/giris${next}`} className="pill hover:text-[var(--text)]">Giriş yap</Link>
      <Link prefetch={false} href="/kayit" className="hidden h-8 items-center rounded bg-[var(--primary)] px-3 text-[11px] font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)] sm:flex">Kayıt ol</Link>
    </div>;
  }

  return <div ref={container} className="relative">
    <button ref={button} type="button" onClick={() => setOpen((value) => !value)} aria-haspopup="menu" aria-expanded={open} aria-controls="account-menu" aria-label={`Hesap menüsü: ${account.display_name || account.email}`} className="grid h-8 w-8 place-items-center rounded-full bg-[var(--primary-soft)] text-[11px] font-semibold text-[var(--primary)] transition hover:ring-2 hover:ring-[var(--primary-soft)]">{accountInitials(account)}</button>
    {open && <div id="account-menu" role="menu" className="panel-flat absolute right-0 top-10 z-50 w-64 p-1.5 shadow-lg">
      <div className="border-b px-3 pb-2.5 pt-1.5" style={{ borderColor: "var(--border)" }}>
        <p className="truncate text-sm font-semibold">{account.display_name || account.email}</p>
        <p className="truncate text-[11px] text-[var(--text-muted)]">{account.email}</p>
        {account.role === "admin" && <span className="pill mt-1.5">Yönetici</span>}
      </div>
      <div className="py-1">
        <Link role="menuitem" prefetch={false} href="/hesap" className={itemClass}>Hesabım</Link>
        <Link role="menuitem" prefetch={false} href="/hesap/bildirimler" className={itemClass}>Bildirimler</Link>
        <Link role="menuitem" prefetch={false} href="/portfoylerim" className={itemClass}>Portföylerim</Link>
        <Link role="menuitem" prefetch={false} href="/izleme-listesi" className={itemClass}>İzleme listem</Link>
        {account.role === "admin" && <Link role="menuitem" prefetch={false} href="/sistem" className={itemClass}>Sistem sağlığı</Link>}
      </div>
      <div className="border-t pt-1" style={{ borderColor: "var(--border)" }}>
        <LogoutForm className={itemClass}>Çıkış yap</LogoutForm>
      </div>
    </div>}
  </div>;
}
