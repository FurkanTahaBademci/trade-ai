import "server-only";

import { headers } from "next/headers";
import { adminAuthState } from "./admin-auth";

export async function requireAdminRequest(): Promise<void> {
  const state = adminAuthState((await headers()).get("authorization"));
  if (state === "disabled" || state === "authorized") return;
  throw new Error(state === "misconfigured" ? "Yönetici erişimi yapılandırılmamış" : "Yetkisiz yönetici isteği");
}
