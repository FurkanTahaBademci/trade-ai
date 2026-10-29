"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Sunucu bileşenini aralıklarla yeniden çizer (ör. kuyruktaki backtest bitene kadar). */
export function AutoRefresh({ intervalMs }: { intervalMs: number }) {
  const router = useRouter();
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") router.refresh();
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [router, intervalMs]);
  return null;
}
