import { logoutAction } from "@/app/giris/actions";
import { adminConfig } from "@/lib/admin-auth";

/** Yönetim ekranlarının başlığında gösterilir; giriş kapalıysa (yerel geliştirme) görünmez. */
export function LogoutButton() {
  if (adminConfig().mode !== "enabled") return null;
  return <form action={logoutAction}>
    <button className="pill hover:text-[var(--text)]" type="submit">Çıkış yap</button>
  </form>;
}
