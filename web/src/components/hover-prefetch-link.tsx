"use client";

import Link from "next/link";
import { useState, type ComponentProps } from "react";

// Görünür olunca değil, ilk hover/odakta prefetch eder. Kenar menüsü her sayfada
// ~15 bağlantı gösteriyor; varsayılan davranış her açılışta o kadar sunucu
// isteği demekti. `prefetch={false}` verilirse hover'da da prefetch yapılmaz.
export function HoverPrefetchLink({ prefetch, onMouseEnter, onFocus, ...props }: ComponentProps<typeof Link>) {
  const [active, setActive] = useState(false);
  return <Link
    {...props}
    prefetch={prefetch !== false && active ? null : false}
    onMouseEnter={(event) => { setActive(true); onMouseEnter?.(event); }}
    onFocus={(event) => { setActive(true); onFocus?.(event); }}
  />;
}
