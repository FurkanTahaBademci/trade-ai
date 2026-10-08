import "server-only";

import { cookies } from "next/headers";
import { ADMIN_SESSION_COOKIE, adminAuthState } from "./admin-auth";

/** Server Action'lar proxy'ye güvenmez; oturumu her çağrıda yeniden doğrular. */
export async function requireAdminRequest(): Promise<void> {
  const state = adminAuthState((await cookies()).get(ADMIN_SESSION_COOKIE)?.value);
  if (state === "disabled" || state === "authorized") return;
  throw new Error(state === "misconfigured" ? "Yönetici erişimi yapılandırılmamış" : "Yetkisiz yönetici isteği");
}
