import type { MetadataRoute } from "next";

// Yönetim ekranları ve veri uçları taranmaz; araştırma sayfaları açıktır.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/api/", "/sistem", "/backtest", "/giris"] },
  };
}
