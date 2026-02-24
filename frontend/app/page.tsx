"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Users, CalendarDays, Settings2, Wand2, CalendarCheck,
  BarChart3, Download, AlertTriangle,
} from "lucide-react";
import {
  getEmployees, getRequestStatus, getRequirements, getSchedules,
  type Schedule,
} from "@/lib/api";

export default function DashboardPage() {
  const today = new Date();
  const currentMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
  const nextMonth = `${today.getFullYear()}-${String(today.getMonth() + 2).padStart(2, "0")}`;

  const [empCount, setEmpCount] = useState(0);
  const [reqStatus, setReqStatus] = useState({ total: 0, done: 0 });
  const [reqDays, setReqDays] = useState(0);
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [alerts, setAlerts] = useState<string[]>([]);

  useEffect(() => {
    (async () => {
      const [emps, statuses, reqs, schedules] = await Promise.all([
        getEmployees(),
        getRequestStatus(nextMonth),
        getRequirements(nextMonth),
        getSchedules(nextMonth),
      ]);

      setEmpCount(emps.length);
      setReqStatus({ total: statuses.length, done: statuses.filter((s) => s.has_request).length });
      setReqDays(new Set(reqs.map((r) => r.date)).size);
      setSchedule(schedules.length > 0 ? schedules[0] : null);

      const newAlerts: string[] = [];
      const unsubmitted = statuses.filter((s) => !s.has_request);
      if (unsubmitted.length > 0) {
        newAlerts.push(`希望未入力: ${unsubmitted.map((s) => s.employee_name).join(", ")}`);
      }
      if (reqs.length === 0) {
        newAlerts.push("日別必要人数が設定されていません");
      }
      setAlerts(newAlerts);
    })();
  }, []);

  const statusLabel = (s: Schedule | null) => {
    if (!s) return { label: "未生成", variant: "secondary" as const };
    switch (s.status) {
      case "published": return { label: "公開中", variant: "success" as const };
      case "confirmed": return { label: "確定", variant: "default" as const };
      case "preview": return { label: "プレビュー", variant: "secondary" as const };
      default: return { label: "下書き", variant: "secondary" as const };
    }
  };

  const st = statusLabel(schedule);

  const navCards = [
    { href: "/staff", icon: Users, label: "スタッフ管理", desc: `${empCount}名登録` },
    { href: "/requests", icon: CalendarDays, label: "希望入力", desc: `${reqStatus.done}/${reqStatus.total}名入力済` },
    { href: "/requirements", icon: Settings2, label: "必要人数設定", desc: `${reqDays}日設定済` },
    { href: "/generate", icon: Wand2, label: "シフト自動生成", desc: "最適化エンジンで自動生成" },
    { href: "/schedule", icon: CalendarCheck, label: "シフト表", desc: "マトリクス表示・手動調整" },
    { href: "/reports", icon: BarChart3, label: "集計・レポート", desc: "スタッフ別集計・公平性" },
    { href: "/export", icon: Download, label: "シフト出力", desc: "CSV/Excel/PDF出力" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">ダッシュボード</h1>

      <div className="flex gap-4 items-center">
        <span className="text-muted-foreground">来月 ({nextMonth}) のシフト状況:</span>
        <Badge variant={st.variant}>{st.label}</Badge>
      </div>

      {alerts.length > 0 && (
        <Card className="border-yellow-500">
          <CardHeader>
            <CardTitle className="text-lg text-yellow-600 flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              アラート
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc pl-5 space-y-1 text-sm">
              {alerts.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {navCards.map((item) => (
          <Link key={item.href} href={item.href}>
            <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <item.icon className="h-5 w-5 text-primary" />
                  {item.label}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{item.desc}</p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
