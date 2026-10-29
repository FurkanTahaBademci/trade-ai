"use client";

import { logoutAction } from "@/app/giris/actions";
import { clearLocalWatchlist } from "@/lib/watchlist";

/** Çıkışta bu tarayıcıdaki hesaba ait izleme listesi de silinir (ortak bilgisayar). */
export function LogoutForm({ className, children = "Çıkış yap" }: { className?: string; children?: React.ReactNode }) {
  return <form action={logoutAction} onSubmit={() => clearLocalWatchlist()}>
    <button className={className} type="submit">{children}</button>
  </form>;
}
