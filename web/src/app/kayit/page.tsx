import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { RegisterForm } from "@/components/account-forms";
import { AuthCard } from "@/components/auth-card";
import { currentAccount, serviceRequest } from "@/lib/account-server";

export const metadata: Metadata = { title: "Kayıt ol", robots: { index: false, follow: false } };

type AuthConfig = { registration_mode: "invite" | "open" | "closed"; password_min_length: number };

export default async function RegisterPage() {
  if (await currentAccount()) redirect("/hesap");
  const config = await serviceRequest<AuthConfig>("/api/auth/config");
  const mode = config.ok ? config.data.registration_mode : "invite";
  const footer = <p>Zaten hesabın var mı? <Link href="/giris" className="font-medium text-[var(--primary)]">Giriş yap</Link></p>;

  if (mode === "closed") {
    return <AuthCard eyebrow="Hesap" title="Kayıtlar kapalı" footer={footer}>
      <p className="text-sm leading-6 text-[var(--text-secondary)]">Şu an yeni hesap açılmıyor. Piyasa, sinyal ve haber ekranlarını girişsiz kullanmaya devam edebilirsin.</p>
    </AuthCard>;
  }
  return <AuthCard
    eyebrow={mode === "invite" ? "Kapalı beta · davetle kayıt" : "Hesap"}
    title="Hesap oluştur"
    footer={footer}
    notice={!config.ok && <p role="alert" className="mb-4 text-xs text-[var(--negative)]">{config.message}</p>}
  >
    <RegisterForm inviteRequired={mode === "invite"} passwordMinLength={config.ok ? config.data.password_min_length : 10}/>
  </AuthCard>;
}
