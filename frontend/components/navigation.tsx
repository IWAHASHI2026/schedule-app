"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Users,
  CalendarDays,
  Settings2,
  Wand2,
  CalendarCheck,
  BarChart3,
  Download,
} from "lucide-react";

const navItems = [
  { href: "/", label: "ダッシュボード", icon: LayoutDashboard },
  { href: "/staff", label: "スタッフ管理", icon: Users },
  { href: "/requests", label: "希望入力", icon: CalendarDays },
  { href: "/requirements", label: "必要人数設定", icon: Settings2 },
  { href: "/generate", label: "シフト自動生成", icon: Wand2 },
  { href: "/schedule", label: "シフト表", icon: CalendarCheck },
  { href: "/reports", label: "集計・レポート", icon: BarChart3 },
  { href: "/export", label: "シフト出力", icon: Download },
];

export default function Navigation() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-56 border-r bg-card">
      <div className="flex h-14 items-center border-b px-4">
        <CalendarCheck className="mr-2 h-5 w-5 text-primary" />
        <span className="font-bold text-lg">シフト管理</span>
      </div>
      <nav className="space-y-1 p-3">
        {navItems.map((item) => {
          const isActive =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
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
  );
}
