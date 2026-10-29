import "server-only";

import { cookies } from "next/headers";
import { ADMIN_SESSION_COOKIE, adminAuthState } from "./admin-auth";
import { currentAccount } from "./account-server";

/** Ortam değişkeniyle tanımlı yönetici girişi ya da rolü `admin` olan hesap. */
export async function isAdminRequest(): Promise<boolean> {
  const state = adminAuthState((await cookies()).get(ADMIN_SESSION_COOKIE)?.value);
  if (state === "disabled" || state === "authorized") return true;
  return (await currentAccount())?.role === "admin";
}

/** Server Action'lar proxy'ye güvenmez; oturumu her çağrıda yeniden doğrular. */
export async function requireAdminRequest(): Promise<void> {
  if (await isAdminRequest()) return;
  throw new Error("Yetkisiz yönetici isteği");
}
