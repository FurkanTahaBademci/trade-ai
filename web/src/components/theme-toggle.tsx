"use client";

import { useEffect, useState } from "react";
import { Icon } from "./icon";
import { applyTheme, getStoredTheme, resolveTheme, type Theme } from "@/lib/theme";

export function ThemeToggle() {
  const [mounted, setMounted] = useState(false);
  const [theme, setTheme] = useState<Theme>("system");
  const [resolved, setResolved] = useState<"dark" | "light">("dark");

  useEffect(() => {
    setMounted(true);
    const stored = getStoredTheme();
    setTheme(stored);

    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    setResolved(resolveTheme(stored, mql.matches));

    function handleSystemChange(e: MediaQueryListEvent) {
      if (getStoredTheme() === "system") {
        setResolved(e.matches ? "dark" : "light");
        document.documentElement.setAttribute("data-theme", e.matches ? "dark" : "light");
      }
    }

    function handleThemeEvent(e: Event) {
      const customEvent = e as CustomEvent<{ theme: Theme; resolved: "dark" | "light" }>;
      if (customEvent.detail) {
        setTheme(customEvent.detail.theme);
        setResolved(customEvent.detail.resolved);
      }
    }

    mql.addEventListener("change", handleSystemChange);
    window.addEventListener("trade-ai:theme-change", handleThemeEvent);

    return () => {
      mql.removeEventListener("change", handleSystemChange);
      window.removeEventListener("trade-ai:theme-change", handleThemeEvent);
    };
  }, []);

  function toggleTheme() {
    // Koyu -> Acik, Acik -> Koyu
    const next: Theme = resolved === "dark" ? "light" : "dark";
    setTheme(next);
    const newResolved = applyTheme(next);
    setResolved(newResolved);
  }

  // SSR sirasinda hidrasyon farki yaratmamak icin varsayilan koyu gorunumle basla
  const isLight = mounted && resolved === "light";
  const label = isLight ? "Koyu temaya geç" : "Açık temaya geç";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="icon-button relative"
      aria-label={label}
      title={label}
    >
      <Icon
        name={isLight ? "moon" : "sun"}
        size={17}
        className="transition-transform duration-200 hover:rotate-12"
      />
    </button>
  );
}
