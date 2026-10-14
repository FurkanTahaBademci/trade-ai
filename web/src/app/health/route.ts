import { APP_COMMIT, APP_VERSION } from "@/lib/build-info";

export function GET() {
  return Response.json({ status: "ok", service: "web", version: APP_VERSION, commit: APP_COMMIT || null });
}
