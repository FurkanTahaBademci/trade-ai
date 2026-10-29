import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { RegisterForm } from "@/components/account-forms";
import { AuthCard, AuthNotice } from "@/components/auth-card";
import { GoogleSignupForm, OrDivider } from "@/components/google-sign-in";
import { currentAccount, serviceRequest } from "@/lib/account-server";
import { googleMessage } from "@/lib/oauth";

export const metadata: Metadata = { title: "Kayıt ol", robots: { index: false, follow: false } };

type AuthConfig = { registration_mode: "invite" | "open" | "closed"; password_min_length: number; google_enabled?: boolean };

export default async function RegisterPage({ searchParams }: { searchParams: Promise<{ google?: string }> }) {
  if (await currentAccount()) redirect("/hesap");
  const [config, params] = await Promise.all([serviceRequest<AuthConfig>("/api/auth/config"), searchParams]);
  const googleError = googleMessage(params.google);
  const mode = config.ok ? config.data.registration_mode : "invite";
  const footer = <p>Zaten hesabın var mı? <Link href="/giris" className="font-medium text-[var(--primary)]">Giriş yap</Link></p>;

  if (mode === "closed") {
    return <AuthCard eyebrow="Hesap" title="Kayıtlar kapalı" footer={footer} notice={googleError && <AuthNotice tone="negative">{googleError}</AuthNotice>}>
      <p className="text-sm leading-6 text-[var(--text-secondary)]">Şu an yeni hesap açılmıyor. Piyasa, sinyal ve haber ekranlarını girişsiz kullanmaya devam edebilirsin.</p>
    </AuthCard>;
  }
  return <AuthCard
    eyebrow={mode === "invite" ? "Kapalı beta · davetle kayıt" : "Hesap"}
    title="Hesap oluştur"
    footer={footer}
    notice={googleError ? <AuthNotice tone="negative">{googleError}</AuthNotice> : !config.ok && <p role="alert" className="mb-4 text-xs text-[var(--negative)]">{config.message}</p>}
  >
    {config.ok && config.data.google_enabled && <><GoogleSignupForm inviteRequired={mode === "invite"}/><OrDivider label="ya da e-postayla kayıt ol"/></>}
    <RegisterForm inviteRequired={mode === "invite"} passwordMinLength={config.ok ? config.data.password_min_length : 10}/>
  </AuthCard>;
}
