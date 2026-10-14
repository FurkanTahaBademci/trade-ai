import { readFileSync } from "node:fs";

// Surumun tek kaynagi kokteki VERSION dosyasidir; `make release` onu
// package.json'a da yazar. Docker build baglami yalniz web/ oldugu icin
// buradan okunur.
const { version } = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8"));
// Coolify'da "Include Source Commit in Build" aciksa SOURCE_COMMIT build
// arg'i olarak gelir (docker-compose.yml). Yoksa surum etiketi tek basina kalir.
const rawCommit = (process.env.SOURCE_COMMIT ?? "").trim();
const commit = /^[0-9a-f]{7,40}$/i.test(rawCommit) ? rawCommit.slice(0, 7).toLowerCase() : "";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  env: {
    APP_VERSION: version,
    APP_COMMIT: commit,
  },
  // Yeni surum yayinlaninca acik sekmeler eski JS ile Server Action cagirmasin:
  // kimlik degisince Next istemci gezinmesini tam sayfa yenilemeye cevirir.
  // Commit yoksa her build ayri kimlik alir.
  // Next yalniz harf, rakam, "-" ve "_" kabul eder (0.3.0 -> 0_3_0).
  deploymentId: `${version.replace(/[^a-zA-Z0-9_-]/g, "_")}-${commit || Date.now().toString(36)}`,
  reactStrictMode: true,
  poweredByHeader: false,
  // Coolify sunucusu birden fazla servisi ayni anda build ediyor. Host CPU
  // sayisini oldugu gibi kullanan Next build, bu kucuk VPS'te 15 worker acip
  // swap/disk baskisi olusturuyordu. CI ve production build'ini ongorulebilir
  // bir kaynak sinirinda tut.
  experimental: {
    cpus: 2,
  },
  async headers() {
    return [{
      source: "/(.*)",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      ],
    }];
  },
};

export default nextConfig;
