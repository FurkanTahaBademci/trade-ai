import { timingSafeEqual } from "node:crypto";

export type AdminAuthState = "disabled" | "misconfigured" | "authorized" | "unauthorized";

type AuthEnvironment = {
  NODE_ENV?: string;
  WEB_ADMIN_USERNAME?: string;
  WEB_ADMIN_PASSWORD?: string;
  ADMIN_API_TOKEN?: string;
};

function safeEqual(left: string, right: string): boolean {
  const leftBytes = Buffer.from(left);
  const rightBytes = Buffer.from(right);
  return leftBytes.length === rightBytes.length && timingSafeEqual(leftBytes, rightBytes);
}

function parseBasicAuthorization(header: string | null): { username: string; password: string } | null {
  if (!header?.startsWith("Basic ")) return null;
  try {
    const decoded = Buffer.from(header.slice(6), "base64").toString("utf8");
    const separator = decoded.indexOf(":");
    if (separator < 0) return null;
    return { username: decoded.slice(0, separator), password: decoded.slice(separator + 1) };
  } catch {
    return null;
  }
}

export function adminAuthState(
  authorization: string | null,
  env: AuthEnvironment = process.env,
): AdminAuthState {
  const explicitlyConfigured = Boolean(env.WEB_ADMIN_PASSWORD);
  if (env.NODE_ENV !== "production" && !explicitlyConfigured) return "disabled";

  const expectedPassword = env.WEB_ADMIN_PASSWORD || env.ADMIN_API_TOKEN;
  if (!expectedPassword) return "misconfigured";

  const credentials = parseBasicAuthorization(authorization);
  if (!credentials) return "unauthorized";
  const expectedUsername = env.WEB_ADMIN_USERNAME || "admin";
  const usernameMatches = safeEqual(credentials.username, expectedUsername);
  const passwordMatches = safeEqual(credentials.password, expectedPassword);
  return usernameMatches && passwordMatches
    ? "authorized"
    : "unauthorized";
}
