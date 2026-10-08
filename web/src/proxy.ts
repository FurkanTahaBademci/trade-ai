import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { ADMIN_SESSION_COOKIE, adminAuthState, safeNextPath } from "./lib/admin-auth";

export function proxy(request: NextRequest) {
  const state = adminAuthState(request.cookies.get(ADMIN_SESSION_COOKIE)?.value);
  if (request.nextUrl.pathname === "/giris") {
    // Zaten girişli (veya giriş kapalı) kullanıcıyı formu göstermeden hedefe gönder.
    if (state !== "disabled" && state !== "authorized") return NextResponse.next();
    return NextResponse.redirect(new URL(safeNextPath(request.nextUrl.searchParams.get("next")), request.url));
  }
  if (state === "disabled" || state === "authorized") return NextResponse.next();

  if (state === "misconfigured") {
    return new NextResponse("Yönetici erişimi yapılandırılmamış. WEB_ADMIN_PASSWORD ayarlayın (docs/ADMIN.md).", {
      status: 503,
      headers: { "Cache-Control": "no-store", "Content-Type": "text/plain; charset=utf-8" },
    });
  }
  const login = new URL("/giris", request.url);
  login.searchParams.set("next", `${request.nextUrl.pathname}${request.nextUrl.search}`);
  const response = NextResponse.redirect(login);
  response.headers.set("Cache-Control", "no-store");
  return response;
}

export const config = {
  matcher: ["/sistem/:path*", "/backtest/:path*", "/giris"],
};
