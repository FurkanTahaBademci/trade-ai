"use client";

import { useEffect } from "react";

/** Takvim açıldığında listeyi "Bugün" işaretine kaydırır; adres çubuğunda başka bir çapa varsa dokunmaz. */
export function ScrollToToday({ targetId }: { targetId: string }) {
  useEffect(() => {
    if (window.location.hash && window.location.hash !== `#${targetId}`) return;
    // Yönlendirici sayfa geçişinde kaydırmayı başa alabilir; kısa bir gecikmeyle tekrar denenir.
    // Kullanıcı bu arada kendisi kaydırdıysa dokunulmaz.
    let done = false;
    const scroll = () => {
      if (done) return;
      const target = document.getElementById(targetId);
      if (!target) return;
      if (Math.abs(target.getBoundingClientRect().top) < 120) return;
      // Hedefte değiliz ama sayfa başta da değil: kullanıcı kaydırmış.
      if (window.scrollY > 40) { done = true; return; }
      target.scrollIntoView({ block: "start" });
    };
    const frame = requestAnimationFrame(scroll);
    const timers = [150, 500].map((delay) => window.setTimeout(scroll, delay));
    return () => { done = true; cancelAnimationFrame(frame); timers.forEach(clearTimeout); };
  }, [targetId]);
  return null;
}
