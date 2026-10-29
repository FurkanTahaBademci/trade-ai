import type { Metadata } from "next";
import Link from "next/link";
import { ResendVerificationForm, VerifyEmailForm } from "@/components/account-forms";
import { AuthCard } from "@/components/auth-card";

export const metadata: Metadata = { title: "E-posta doğrulama", robots: { index: false, follow: false }, referrer: "no-referrer" };

export default async function VerifyEmailPage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token } = await searchParams;
  const footer = <p><Link href="/giris" className="font-medium text-[var(--primary)]">Girişe dön</Link></p>;
  // Doğrulama tek tıkla değil, düğmeyle yapılır: e-posta tarayıcılarının
  // bağlantı ön izlemesi (GET) token'ı tüketmesin.
  return <AuthCard eyebrow="Hesap" title="E-posta doğrulama" footer={footer}>
    {token && <div className="mb-6"><p className="mb-4 text-xs leading-5 text-[var(--text-secondary)]">Hesabını etkinleştirmek için düğmeye bas.</p><VerifyEmailForm token={token}/></div>}
    <div className={token ? "border-t pt-5" : ""} style={token ? { borderColor: "var(--border)" } : undefined}>
      <p className="mb-4 text-xs leading-5 text-[var(--text-secondary)]">{token ? "Bağlantı çalışmadıysa yenisini iste:" : "Doğrulama e-postası gelmediyse ya da bağlantının süresi dolduysa yenisini iste."}</p>
      <ResendVerificationForm/>
    </div>
  </AuthCard>;
}
