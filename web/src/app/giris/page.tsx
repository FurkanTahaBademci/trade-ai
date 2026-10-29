import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { LoginForm } from "@/components/account-forms";
import { AuthCard, AuthNotice } from "@/components/auth-card";
import { GoogleLoginButton, OrDivider } from "@/components/google-sign-in";
import { safeNextPath } from "@/lib/admin-auth";
import { currentAccount, serviceRequest } from "@/lib/account-server";
import { googleMessage } from "@/lib/oauth";

export const metadata: Metadata = { title: "Giriş", robots: { index: false, follow: false } };

const NOTICES: Record<string, string> = {
  cikis: "Oturum kapatıldı.",
  dogrulandi: "E-posta adresin doğrulandı. Şimdi giriş yapabilirsin.",
  sifirlandi: "Parolan değiştirildi. Yeni parolanla giriş yap.",
  silindi: "Hesabın ve tüm verilerin silindi.",
};

export default async function LoginPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const params = await searchParams;
  // Boş `next`, girişten sonra rol bazlı varsayılana (yönetici → /sistem, kullanıcı → /) gider.
  const next = params.next ? safeNextPath(params.next, "") : "";
  const account = await currentAccount();
  if (account) redirect(safeNextPath(next, account.role === "admin" ? "/sistem" : "/"));
  const notice = Object.keys(NOTICES).find((key) => params[key]);
  const googleError = googleMessage(params.google);
  const config = await serviceRequest<{ google_enabled?: boolean }>("/api/auth/config");
  const google = config.ok && config.data.google_enabled === true;

  return <AuthCard
    eyebrow="Hesap"
    title="Giriş yap"
    notice={googleError ? <AuthNotice tone="negative">{googleError}</AuthNotice> : notice && <AuthNotice>{NOTICES[notice]}</AuthNotice>}
    footer={<>
      <p>Hesabın yok mu? <Link href="/kayit" className="font-medium text-[var(--primary)]">Kayıt ol</Link></p>
      <p><Link href="/sifremi-unuttum" className="font-medium text-[var(--primary)]">Parolamı unuttum</Link></p>
      <p className="pt-1 text-[11px] leading-5">Piyasa, sinyal ve haber ekranları giriş gerektirmez. Hesapla izleme listeni saklar, kendi paper portföylerini ve backtest koşularını kurarsın.</p>
    </>}
  >
    {google && <><GoogleLoginButton next={next}/><OrDivider label="ya da e-postayla"/></>}
    <LoginForm next={next}/>
  </AuthCard>;
}
