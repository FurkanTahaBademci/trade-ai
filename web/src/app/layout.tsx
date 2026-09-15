import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import "./globals.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: { default: "TradeAI", template: "%s · TradeAI" },
  description: "BIST piyasa istihbaratı ve analiz terminali",
};

const themeScript = `(function(){try{var t=localStorage.getItem("trade-ai:theme");var d=t==="light"?"light":(t==="dark"?"dark":(window.matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"));document.documentElement.setAttribute("data-theme",d);}catch(e){}})();`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="tr" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen antialiased"><AppShell>{children}</AppShell></body>
    </html>
  );
}

