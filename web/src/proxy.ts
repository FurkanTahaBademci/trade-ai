import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { adminAuthState } from "./lib/admin-auth";

export function proxy(request: NextRequest) {
  const state = adminAuthState(request.headers.get("authorization"));
  if (state === "disabled" || state === "authorized") return NextResponse.next();

  if (state === "misconfigured") {
    return new NextResponse("Yönetici erişimi yapılandırılmamış.", {
      status: 503,
      headers: { "Cache-Control": "no-store" },
    });
  }
  return new NextResponse("Bu alan yönetici kimlik doğrulaması gerektirir.", {
    status: 401,
    headers: {
      "Cache-Control": "no-store",
      "WWW-Authenticate": 'Basic realm="TradeAI Yönetim", charset="UTF-8"',
    },
  });
}

export const config = {
  matcher: ["/sistem/:path*", "/backtest/:path*"],
};
