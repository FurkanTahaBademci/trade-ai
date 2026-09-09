/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
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
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      ],
    }];
  },
};

export default nextConfig;
