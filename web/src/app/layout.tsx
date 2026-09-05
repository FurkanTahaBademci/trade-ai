import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "trade-ai",
  description: "BIST piyasa istihbarati ve paper trading dashboard'u",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="tr">
      <body className="min-h-screen font-sans antialiased">{children}</body>
    </html>
  );
}
