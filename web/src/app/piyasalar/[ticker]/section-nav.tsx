"use client";

import { useEffect, useRef, useState } from "react";

export type SectionLink = { id: string; label: string };

// Üst başlık (h-14) + bu çubuğun yüksekliği; bölüm üst kenarı bu çizgiyi geçince aktif sayılır.
const ACTIVE_LINE_PX = 132;

export function SectionNav({ sections }: { sections: SectionLink[] }) {
  const [active, setActive] = useState(sections[0]?.id ?? "");
  const navRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      let current = sections[0]?.id ?? "";
      for (const { id } of sections) {
        // Suspense iskeleti ile gerçek içerik kısa süre aynı id'yi taşıyabilir; görünür olanı al.
        const element = [...document.querySelectorAll<HTMLElement>(`[id="${id}"]`)].find((node) => node.offsetParent !== null);
        if (element && element.getBoundingClientRect().top <= ACTIVE_LINE_PX) current = id;
      }
      // Sayfanın sonuna gelindiğinde son bölüm kısa olsa da aktif görünsün.
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) current = sections.at(-1)?.id ?? current;
      setActive(current);
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
    update();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [sections]);

  // Mobilde yatay kaydırılan çubukta aktif bağlantıyı görünür tut (sayfayı kaydırmadan).
  useEffect(() => {
    const nav = navRef.current;
    const link = nav?.querySelector<HTMLElement>(`[data-section="${active}"]`);
    if (!nav || !link) return;
    const left = link.offsetLeft - nav.offsetLeft;
    if (left < nav.scrollLeft || left + link.offsetWidth > nav.scrollLeft + nav.clientWidth) {
      nav.scrollTo({ left: Math.max(0, left - 16), behavior: "smooth" });
    }
  }, [active]);

  return <div className="sticky top-14 z-20 -mx-3 mb-6 border-b border-[var(--border)] bg-[var(--background)] px-3 py-2 sm:-mx-4 sm:px-4 lg:-mx-5 lg:px-5">
    <nav ref={navRef} aria-label="Sayfa bölümleri" className="flex gap-2 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {sections.map(({ id, label }) => {
        const current = id === active;
        return <a key={id} href={`#${id}`} data-section={id} aria-current={current ? "location" : undefined} onClick={() => setActive(id)} className={`pill whitespace-nowrap transition hover:text-[var(--primary)] ${current ? "pill-primary font-semibold" : ""}`}>{label}</a>;
      })}
    </nav>
  </div>;
}
