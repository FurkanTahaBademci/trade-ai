import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { ADMIN_SESSION_COOKIE, adminAuthState, safeNextPath } from "./lib/admin-auth";
import { type AccountState, fetchAccountState, SESSION_COOKIE } from "./lib/account";

function apiBase() {
  return process.env.API_INTERNAL_URL ?? "http://localhost:8000";
}

function noStore(response: NextResponse): NextResponse {
  response.headers.set("Cache-Control", "no-store");
  return response;
}

function toLogin(request: NextRequest): NextResponse {
  const login = new URL("/giris", request.url);
  login.searchParams.set("next", `${request.nextUrl.pathname}${request.nextUrl.search}`);
  return noStore(NextResponse.redirect(login));
}

/**
 * /giris, /hesap ve yönetim sayfalarının kapısı. Yönetici; ortam değişkeniyle
 * tanımlı yönetici girişi ya da rolü `admin` olan bir hesaptır. Sayfalar ve
 * Server Action'lar bu kontrole güvenmez, oturumu kendileri yeniden doğrular.
 */
export async function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname;
  const adminState = adminAuthState(request.cookies.get(ADMIN_SESSION_COOKIE)?.value);
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  const account: AccountState = token ? await fetchAccountState(token, apiBase()) : { state: "invalid" };
  const signedIn = account.state === "valid";
  const accountIsAdmin = account.state === "valid" && account.account.role === "admin";
  const respond = (response: NextResponse) => {
    // Süresi dolmuş/iptal edilmiş oturum çerezi temizlenir (yoksa /giris ↔ /hesap döngüsü olur).
    if (token && account.state === "invalid") response.cookies.delete(SESSION_COOKIE);
    return response;
  };

  if (path === "/giris") {
    if (!signedIn && adminState !== "authorized") return respond(NextResponse.next());
    const fallback = signedIn && !accountIsAdmin ? "/" : "/sistem";
    return respond(NextResponse.redirect(new URL(safeNextPath(request.nextUrl.searchParams.get("next"), fallback), request.url)));
  }
  if (path === "/hesap" || path.startsWith("/hesap/")) {
    return respond(signedIn ? NextResponse.next() : toLogin(request));
  }

  if (adminState === "authorized" || adminState === "disabled" || accountIsAdmin) return respond(NextResponse.next());
  // Girişli ama yönetici olmayan kullanıcı girişe yönlendirilmez (döngü olur).
  if (signedIn) return noStore(NextResponse.rewrite(new URL("/yetkisiz", request.url), { status: 403 }));
  return respond(toLogin(request));
}

export const config = {
  matcher: ["/sistem/:path*", "/backtest/:path*", "/giris", "/hesap/:path*"],
};
