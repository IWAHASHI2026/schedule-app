"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { getReport, type Report } from "@/lib/api";

export default function ReportsPage() {
  const today = new Date();
  const defaultMonth = `${today.getFullYear()}-${String(today.getMonth() + 2).padStart(2, "0")}`;
  const [month, setMonth] = useState(defaultMonth);
  const [report, setReport] = useState<Report | null>(null);

  const load = async () => {
    const r = await getReport(month);
    setReport(r);
  };

  useEffect(() => { load(); }, [month]);

  const maxWork = report ? Math.max(...report.employees.map((e) => e.total_work_days), 1) : 1;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">集計・レポート</h1>

      <div>
        <Label>対象月</Label>
        <Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="mt-1 w-44" />
      </div>

      {report && report.employees.length > 0 ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">スタッフ別集計</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="py-2 px-3 text-left">スタッフ</th>
                      <th className="py-2 px-3 text-center">出勤日数</th>
                      <th className="py-2 px-3 text-center">休日数</th>
                      <th className="py-2 px-3 text-center">希望出勤</th>
                      {Object.keys(report.employees[0]?.job_type_counts || {}).map((jt) => (
                        <th key={jt} className="py-2 px-3 text-center">{jt}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {report.employees.map((emp) => (
                      <tr key={emp.employee_id} className="border-b hover:bg-muted/50">
                        <td className="py-2 px-3 font-medium">{emp.employee_name}</td>
                        <td className="py-2 px-3 text-center">{emp.total_work_days}</td>
                        <td className="py-2 px-3 text-center">{emp.total_days_off}</td>
                        <td className="py-2 px-3 text-center">{emp.requested_work_days === "max" ? "なるべく多く" : emp.requested_work_days ?? "-"}</td>
                        {Object.entries(emp.job_type_counts).map(([jt, count]) => (
                          <td key={jt} className="py-2 px-3 text-center">{count}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">出勤日数の公平性</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex gap-4 text-sm text-muted-foreground mb-4">
                  <span>最多: {report.fairness_max}日</span>
                  <span>最少: {report.fairness_min}日</span>
                  <span>差: {report.fairness_diff}日</span>
                </div>
                {report.employees.map((emp) => (
                  <div key={emp.employee_id} className="flex items-center gap-3">
                    <span className="w-24 text-sm truncate">{emp.employee_name}</span>
                    <div className="flex-1 bg-muted rounded-full h-6 relative">
                      <div
                        className="bg-primary h-6 rounded-full flex items-center justify-end pr-2"
                        style={{ width: `${(emp.total_work_days / maxWork) * 100}%` }}
                      >
                        <span className="text-xs text-primary-foreground font-medium">
                          {emp.total_work_days}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </>
      ) : (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            レポートデータがありません。シフトを生成してください。
          </CardContent>
        </Card>
      )}
    </div>
  );
}
