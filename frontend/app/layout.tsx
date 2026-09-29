import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import AppShell from "@/components/app-shell";
import DbStatusBanner from "@/components/db-status-banner";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "シフト管理システム",
  description: "シフト表自動作成Webアプリケーション",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body className={inter.className}>
        <DbStatusBanner />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
