"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Users,
  CalendarDays,
  CalendarOff,
  Settings2,
  Wand2,
  CalendarCheck,
  BarChart3,
  Download,
  Database,
  Menu,
  X,
} from "lucide-react";

const navItems = [
  { href: "/", label: "ダッシュボード", icon: LayoutDashboard },
  { href: "/staff", label: "スタッフ管理", icon: Users },
  { href: "/holidays", label: "休日設定", icon: CalendarOff },
  { href: "/requests", label: "希望入力", icon: CalendarDays },
  { href: "/requirements", label: "必要人数設定", icon: Settings2 },
  { href: "/generate", label: "シフト自動生成", icon: Wand2 },
  { href: "/schedule", label: "シフト表", icon: CalendarCheck },
  { href: "/reports", label: "集計・レポート", icon: BarChart3 },
  { href: "/export", label: "シフト出力", icon: Download },
  { href: "/backup", label: "データ管理", icon: Database },
];

// Tailwind の md ブレークポイント。これ以上の幅ではサイドバーを常時表示する
const DESKTOP_QUERY = "(min-width: 768px)";

export default function Navigation() {
  const pathname = usePathname();
  // スマホ幅でのメニューの開閉（md 以上では常時表示のため使われない）
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // 画面の回転などで PC 幅になったら、開いたままのメニュー状態を解除する
  useEffect(() => {
    const mq = window.matchMedia(DESKTOP_QUERY);
    const onChange = () => {
      if (mq.matches) setOpen(false);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  // メニューを開いている間は背面のページをスクロールさせない
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-40 flex h-12 items-center gap-2 border-b bg-card px-2 md:hidden print:hidden">
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="メニューを開く"
          aria-expanded={open}
          className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        >
          <Menu className="h-5 w-5" />
        </button>
        <CalendarCheck className="h-5 w-5 text-primary" />
        <span className="font-bold">シフト管理</span>
      </header>

      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-56 overflow-y-auto border-r bg-card transition-[transform,visibility] duration-200 md:visible md:z-40 md:translate-x-0 print:hidden",
          open ? "visible translate-x-0" : "invisible -translate-x-full"
        )}
      >
        <div className="flex h-14 items-center border-b px-4">
          <CalendarCheck className="mr-2 h-5 w-5 text-primary" />
          <span className="font-bold text-lg">シフト管理</span>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="メニューを閉じる"
            className="ml-auto rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground md:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="space-y-1 p-3">
          {navItems.map((item) => {
            const isActive =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
    </>
  );
}
