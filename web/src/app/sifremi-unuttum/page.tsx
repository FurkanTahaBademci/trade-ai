import type { Metadata } from "next";
import Link from "next/link";
import { ForgotPasswordForm } from "@/components/account-forms";
import { AuthCard } from "@/components/auth-card";

export const metadata: Metadata = { title: "Parolamı unuttum", robots: { index: false, follow: false } };

export default function ForgotPasswordPage() {
  return <AuthCard eyebrow="Hesap" title="Parolamı unuttum" footer={<p><Link href="/giris" className="font-medium text-[var(--primary)]">Girişe dön</Link></p>}>
    <p className="mb-4 text-xs leading-5 text-[var(--text-secondary)]">Kayıtlı e-posta adresini yaz; parolanı sıfırlaman için 1 saat geçerli bir bağlantı gönderelim.</p>
    <ForgotPasswordForm/>
  </AuthCard>;
}
