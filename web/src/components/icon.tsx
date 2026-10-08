import type { SVGProps } from "react";

export type IconName = "home" | "markets" | "news" | "kap" | "ai" | "funds" | "search" | "bell" | "menu" | "close" | "arrow" | "trend" | "spark" | "building" | "file" | "clock" | "check" | "external" | "chevron" | "activity" | "star" | "sun" | "moon" | "calendar" | "download";

const paths: Record<IconName, React.ReactNode> = {
  home: <><path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9M9 20v-6h6v6"/></>,
  markets: <><path d="M4 19V9m5 10V5m5 14v-7m5 7V3"/></>,
  news: <><path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h5M8 16h8"/></>,
  kap: <><path d="M6 3h9l3 3v15H6z"/><path d="M15 3v4h4M9 12h6M9 16h6"/></>,
  ai: <><path d="M12 2v3m0 14v3M4.93 4.93l2.12 2.12m9.9 9.9 2.12 2.12M2 12h3m14 0h3M4.93 19.07l2.12-2.12m9.9-9.9 2.12-2.12"/><circle cx="12" cy="12" r="4"/></>,
  funds: <><path d="M3 20h18M5 17h14M6 8v9m4-9v9m4-9v9m4-9v9M4 8h16L12 3z"/></>,
  search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16"/>, close: <path d="m6 6 12 12M18 6 6 18"/>,
  arrow: <><path d="M5 12h14M14 7l5 5-5 5"/></>, trend: <><path d="m3 17 6-6 4 4 8-9"/><path d="M15 6h6v6"/></>,
  spark: <path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7z"/>,
  building: <><path d="M4 21h16M6 21V6h12v15M9 10h2m2 0h2m-6 4h2m2 0h2m-4 7v-3h2v3"/></>,
  file: <><path d="M6 3h9l3 3v15H6z"/><path d="M15 3v4h4"/></>, clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  check: <path d="m5 12 4 4L19 6"/>, external: <><path d="M13 5h6v6M19 5l-8 8"/><path d="M17 13v6H5V7h6"/></>, chevron: <path d="m9 18 6-6-6-6"/>,
  activity: <path d="M3 12h4l2-7 4 14 2-7h6"/>,
  star: <path d="m12 2.5 2.95 6.4 6.98.65-5.28 4.7 1.58 6.9L12 17.6l-6.23 3.55 1.58-6.9-5.28-4.7 6.98-.65z"/>,
  sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M6.34 17.66l-1.41 1.41m14.14-14.14-1.41 1.41"/></>,
  moon: <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>,
  calendar: <><path d="M4 6h16v14H4zM4 10h16M8 3v4m8-4v4"/></>,
  download: <><path d="M12 4v11m0 0-4-4m4 4 4-4M5 20h14"/></>,
};


export function Icon({ name, size = 18, ...props }: SVGProps<SVGSVGElement> & { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name]}</svg>;
}
