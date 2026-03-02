"use client";

import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { getReport, getJobTypes, type Report, type JobType } from "@/lib/api";

export default function ReportsPage() {
  const today = new Date();
  const defaultMonth = `${today.getFullYear()}-${String(today.getMonth() + 2).padStart(2, "0")}`;
  const [month, setMonth] = useState(defaultMonth);
  const [report, setReport] = useState<Report | null>(null);
  const [jobTypes, setJobTypes] = useState<JobType[]>([]);

  const load = async () => {
    const [r, jts] = await Promise.all([getReport(month), getJobTypes()]);
    setReport(r);
    setJobTypes(jts);
  };

  useEffect(() => { load(); }, [month]);

  // 仕事種類マスタの順序で表示（sort_order順 = 職人, サブ職人, lkデータ, uv/cpデータ, 手紙, その他）
  const allJobTypes = jobTypes.map((jt) => jt.name);

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
                      <th className="py-2 px-3 text-center border-r-2 border-gray-300">週間上限</th>
                      {allJobTypes.map((jt) => (
                        <th key={jt} className="py-2 px-3 text-center bg-muted/40">{jt}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {report.employees.map((emp) => (
                      <tr key={emp.employee_id} className="border-b hover:bg-muted/50">
                        <td className="py-2 px-3 font-medium">{emp.employee_name}</td>
                        <td className="py-2 px-3 text-center">{emp.total_work_days}</td>
                        <td className="py-2 px-3 text-center">{emp.total_days_off}</td>
                        <td className="py-2 px-3 text-center">{emp.requested_work_days === "max" ? "なるべく多く" : emp.requested_work_days != null ? `${emp.requested_work_days}日以内` : "-"}</td>
                        <td className="py-2 px-3 text-center border-r-2 border-gray-300">{emp.weekly_work_day_limit != null ? `週${emp.weekly_work_day_limit}日以内` : "-"}</td>
                        {allJobTypes.map((jt) => (
                          <td key={jt} className="py-2 px-3 text-center bg-muted/40">{emp.job_type_counts[jt] || ""}</td>
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
              <CardTitle className="text-lg">希望充足コメント</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-1.5">
                {report.employees.map((emp) => (
                  <div key={emp.employee_id} className="flex gap-2 text-sm">
                    <span className="w-28 shrink-0 font-medium">{emp.employee_name}</span>
                    <span className="text-muted-foreground">{emp.comment}</span>
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
