import type { IconName } from "@/components/icon";
import { foldTurkish } from "./turkish";

export type NavItem = {
  label: string;
  href: string;
  icon: IconName;
  /** Yönetici girişi gerektiren sayfa. */
  locked?: boolean;
  /** Global aramada sayfayı bulduran ek kelimeler. */
  keywords?: string;
};

export const NAV_ITEMS: NavItem[] = [
  { label: "Genel Bakış", href: "/", icon: "home", keywords: "ana sayfa özet piyasa özeti" },
  { label: "Piyasalar", href: "/piyasalar", icon: "markets", keywords: "hisseler fiyat bist" },
  { label: "Karşılaştır", href: "/karsilastir", icon: "activity", keywords: "kıyasla şirket karşılaştırma" },
  { label: "Hisse Tarayıcı", href: "/tarayici", icon: "search", keywords: "filtre screener tarama" },
  { label: "İzleme Listesi", href: "/izleme-listesi", icon: "star", keywords: "favori takip watchlist" },
  { label: "Bileşik Sinyaller", href: "/sinyaller", icon: "activity", keywords: "skor sıralama sinyal doğruluk" },
  { label: "Model Portföy", href: "/portfoy", icon: "trend", keywords: "paper portföy pozisyon simülasyon" },
  { label: "Portföylerim", href: "/portfoylerim", icon: "spark", keywords: "kendi portföy paper emir strateji manuel hesap" },
  { label: "Backtest", href: "/backtest", icon: "activity", locked: true, keywords: "geriye dönük test strateji" },
  { label: "Faiz & Makro", href: "/makro", icon: "building", keywords: "tcmb ppk politika faizi enflasyon" },
  { label: "Takvim", href: "/takvim", icon: "calendar", keywords: "temettü genel kurul bilanço ppk olay" },
  { label: "Haber Akışı", href: "/haberler", icon: "news", keywords: "haberler gündem" },
  { label: "KAP Bildirimleri", href: "/kap", icon: "kap", keywords: "bildirim açıklama özel durum" },
  { label: "AI Analizleri", href: "/analizler", icon: "ai", keywords: "yapay zeka değerlendirme etki" },
  { label: "Kurumsal Veriler", href: "/kurumsal", icon: "funds", keywords: "fon tefas akım" },
  { label: "Sistem Sağlığı", href: "/sistem", icon: "activity", locked: true, keywords: "durum yönetim ayarlar" },
];

export const NAV_GROUPS: { label: string; routes: string[] }[] = [
  { label: "01 / PİYASA", routes: ["/", "/piyasalar", "/tarayici", "/izleme-listesi", "/karsilastir"] },
  { label: "02 / ARAŞTIRMA", routes: ["/sinyaller", "/haberler", "/kap", "/analizler", "/makro", "/takvim", "/kurumsal"] },
  { label: "03 / STRATEJİ", routes: ["/portfoy", "/portfoylerim", "/backtest"] },
  { label: "04 / OPERASYON", routes: ["/sistem"] },
];

export function isActiveRoute(href: string, pathname: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

/** Global aramada sayfa eşleşmeleri: önce adı sorguyla başlayanlar, sonra adında veya anahtar kelimelerinde geçenler. */
export function searchPages(query: string, limit = 5): NavItem[] {
  const needle = foldTurkish(query.trim());
  if (!needle) return [];
  const scored: [number, NavItem][] = [];
  for (const item of NAV_ITEMS) {
    const label = foldTurkish(item.label);
    const words = label.split(/\s+/);
    const score = label.startsWith(needle) ? 0 : words.some((word) => word.startsWith(needle)) ? 1 : label.includes(needle) ? 2 : foldTurkish(item.keywords ?? "").includes(needle) ? 3 : -1;
    if (score >= 0) scored.push([score, item]);
  }
  return scored.sort((a, b) => a[0] - b[0]).slice(0, limit).map(([, item]) => item);
}
