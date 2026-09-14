import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import "./globals.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: { default: "TradeAI", template: "%s · TradeAI" },
  description: "BIST piyasa istihbaratı ve analiz terminali",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="tr">
      <body className="min-h-screen antialiased"><AppShell>{children}</AppShell></body>
    </html>
  );
}
