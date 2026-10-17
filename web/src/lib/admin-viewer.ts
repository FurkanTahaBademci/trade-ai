import { cookies } from "next/headers";
import { ADMIN_SESSION_COOKIE, adminAuthState } from "./admin-auth";

/**
 * Herkese açık sayfalarda iç teknik ayrıntıları yalnız yöneticiye göstermek için.
 * Giriş kapalıysa (yerel geliştirme) herkes yönetici sayılır.
 */
export async function isAdminViewer(): Promise<boolean> {
  const state = adminAuthState((await cookies()).get(ADMIN_SESSION_COOKIE)?.value);
  return state === "authorized" || state === "disabled";
}
