"use client";

import { useEffect, useRef, useState } from "react";

export function useChartWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const update = () => {
      const rectW = element.getBoundingClientRect().width;
      const clientW = element.clientWidth;
      const parentW = element.parentElement?.clientWidth;
      const measured = rectW || clientW || parentW || 0;
      if (measured > 0) {
        setWidth(Math.max(240, Math.round(measured)));
      }
    };
    update();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", update);
      return () => window.removeEventListener("resize", update);
    }
    const observer = new ResizeObserver(() => {
      requestAnimationFrame(update);
    });
    observer.observe(element);
    if (element.parentElement) {
      observer.observe(element.parentElement);
    }
    return () => observer.disconnect();
  }, []);
  return { ref, width };
}

export const chartButton = "rounded-lg border border-[var(--border)] px-3 py-2 text-xs text-[var(--text-secondary)] transition hover:bg-[var(--surface-hover)] disabled:cursor-not-allowed disabled:opacity-40";
