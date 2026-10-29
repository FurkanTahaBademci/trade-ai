import { adminConfig } from "@/lib/admin-auth";
import { currentAccount } from "@/lib/account-server";
import { LogoutForm } from "./logout-form";

/** Yönetim ekranlarının başlığında gösterilir; giriş kapalıysa (yerel geliştirme) görünmez. */
export async function LogoutButton() {
  if (adminConfig().mode !== "enabled" && !(await currentAccount())) return null;
  return <LogoutForm className="pill hover:text-[var(--text)]"/>;
}
