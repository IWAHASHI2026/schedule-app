import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Navigation from "@/components/navigation";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "シフト管理システム",
  description: "シフト表自動作成Webアプリケーション",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body className={inter.className}>
        <Navigation />
        <main className="ml-56 min-h-screen p-6">{children}</main>
      </body>
    </html>
  );
}
