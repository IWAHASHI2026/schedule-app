"use client";

import { usePathname } from "next/navigation";
import Navigation from "@/components/navigation";

// 管理用ナビゲーションを出さない公開ページ（スタッフが自分のスマホで開く画面）
const PUBLIC_PATH_PREFIXES = ["/share", "/staff-request"];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublic = PUBLIC_PATH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );

  if (isPublic) {
    return <main className="min-h-screen p-6">{children}</main>;
  }

  return (
    <>
      <Navigation />
      {/* スマホ幅: 上部バーの高さ分だけ上を空ける / md 以上: サイドバーの幅分だけ左を空ける */}
      <main className="min-h-screen px-3 pb-6 pt-16 md:ml-56 md:p-6">{children}</main>
    </>
  );
}
