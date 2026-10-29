import type { Metadata } from "next";
import Link from "next/link";
import { AuthCard } from "@/components/auth-card";

export const metadata: Metadata = { title: "Yetkisiz", robots: { index: false, follow: false } };

/** Girişli ama yönetici olmayan kullanıcı /sistem açınca proxy buraya yönlendirir. */
export default function ForbiddenPage() {
  return <AuthCard eyebrow="Erişim" title="Bu sayfa yöneticilere açık" footer={<p><Link href="/" className="font-medium text-[var(--primary)]">Genel bakışa dön</Link></p>}>
    <p className="text-sm leading-6 text-[var(--text-secondary)]">Sistem ayarları ve kullanıcı yönetimi yalnız yöneticiye açık. Kendi backtest koşuların ve paper portföylerin için menüdeki Backtest ve Portföylerim sayfalarını kullanabilirsin.</p>
  </AuthCard>;
}
