import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { NextRequest } from "next/server";
import { type Account } from "@/lib/account";
import { accountRequest, requestContext, serviceRequest, sessionToken, setSessionCookie } from "@/lib/account-server";
import { DEFAULT_ADMIN_REDIRECT, safeNextPath } from "@/lib/admin-auth";
import { decodeOAuthState, googleErrorPath, OAUTH_COOKIE, OAUTH_COOKIE_PATH } from "@/lib/oauth";

/**
 * Google yetki sayfasından dönüş. `state` çerezdekiyle eşleşmezse istek
 * reddedilir (CSRF); kod API'ye iletilir, giriş/kayıtta oturum çerezi yazılır,
 * bağlamada kimlik mevcut hesaba eklenir. Çerez her durumda silinir.
 */
export async function GET(request: NextRequest) {
  const store = await cookies();
  const saved = decodeOAuthState(store.get(OAUTH_COOKIE)?.value);
  store.delete({ name: OAUTH_COOKIE, path: OAUTH_COOKIE_PATH });
  const params = request.nextUrl.searchParams;
  const mode = saved?.mode ?? "login";
  const code = params.get("code");
  if (params.get("error")) redirect(googleErrorPath(mode, "cancelled"));
  if (!saved || !code || params.get("state") !== saved.state) redirect(googleErrorPath(mode, "state"));
  const exchange = { code, code_verifier: saved.verifier, nonce: saved.nonce };

  if (mode === "link") {
    const token = await sessionToken();
    if (!token) redirect("/giris?next=/hesap");
    const linked = await accountRequest("/api/me/identities/google", token, { body: exchange });
    if (!linked.ok) redirect(googleErrorPath(mode, linked.code ?? "google_failed"));
    redirect(`/hesap?result=ok&message=${encodeURIComponent("Google hesabın bağlandı; artık Google ile de giriş yapabilirsin.")}`);
  }

  const { clientIp, userAgent, secure } = await requestContext();
  const result = await serviceRequest<{ token: string; expires_at: string; user: Account }>("/api/auth/google", {
    body: { ...exchange, invite_code: saved.invite, accept_terms: saved.terms, client_ip: clientIp, user_agent: userAgent },
  });
  if (!result.ok) redirect(googleErrorPath(mode, result.code ?? (result.status >= 500 ? "unavailable" : "google_failed")));
  await setSessionCookie(result.data.token, result.data.expires_at, secure);
  redirect(safeNextPath(saved.next, result.data.user.role === "admin" ? DEFAULT_ADMIN_REDIRECT : "/"));
}
