import type { Metadata } from "next";
import Link from "next/link";
import { ResetPasswordForm } from "@/components/account-forms";
import { AuthCard } from "@/components/auth-card";

export const metadata: Metadata = { title: "Parola sıfırla", robots: { index: false, follow: false }, referrer: "no-referrer" };

export default async function ResetPasswordPage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token } = await searchParams;
  const footer = <p><Link href="/giris" className="font-medium text-[var(--primary)]">Girişe dön</Link></p>;
  if (!token) {
    return <AuthCard eyebrow="Hesap" title="Bağlantı eksik" footer={footer}>
      <p className="text-sm leading-6 text-[var(--text-secondary)]">Bu sayfa e-postadaki parola sıfırlama bağlantısıyla açılır. <Link href="/sifremi-unuttum" className="font-medium text-[var(--primary)]">Yeni bağlantı iste</Link>.</p>
    </AuthCard>;
  }
  return <AuthCard eyebrow="Hesap" title="Yeni parola belirle" footer={footer}>
    <ResetPasswordForm token={token} passwordMinLength={10}/>
  </AuthCard>;
}
