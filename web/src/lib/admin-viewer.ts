import { isAdminRequest } from "./admin-request";

/**
 * Herkese açık sayfalarda iç teknik ayrıntıları yalnız yöneticiye göstermek için.
 * Giriş kapalıysa (yerel geliştirme) herkes yönetici sayılır.
 */
export async function isAdminViewer(): Promise<boolean> {
  return isAdminRequest();
}
