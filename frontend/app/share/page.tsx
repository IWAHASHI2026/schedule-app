"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CalendarCheck } from "lucide-react";
import {
  getEmployees, getJobTypes, getSchedules, getAssignments, getHolidays,
  type Employee, type JobType, type Schedule, type ShiftAssignment, type Holiday,
} from "@/lib/api";

function SharePageContent() {
  const searchParams = useSearchParams();
  const month = searchParams.get("month") || "";
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [jobTypes, setJobTypes] = useState<JobType[]>([]);
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [assignments, setAssignments] = useState<ShiftAssignment[]>([]);
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [loading, setLoading] = useState(true);

  // Hide navigation sidebar for public view
  useEffect(() => {
    const nav = document.querySelector("aside");
    const main = document.querySelector("main");
    if (nav) nav.style.display = "none";
    if (main) main.style.marginLeft = "0";
    return () => {
      if (nav) nav.style.display = "";
      if (main) main.style.marginLeft = "";
    };
  }, []);

  useEffect(() => {
    if (!month) { setLoading(false); return; }
    (async () => {
      try {
        const [emps, jts, scheds, hols] = await Promise.all([
          getEmployees(),
          getJobTypes(),
          getSchedules(month),
          getHolidays(parseInt(month.split("-")[0])),
        ]);
        setEmployees(emps);
        setJobTypes(jts);
        setHolidays(hols);
        // Prefer published > confirmed > any latest
        const target = scheds.find((s) => s.status === "published")
          || scheds.find((s) => s.status === "confirmed")
          || scheds[0];
        if (target) {
          setSchedule(target);
          setAssignments(await getAssignments(target.id));
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [month]);

  if (!month) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">月が指定されていません。</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">読み込み中...</p>
      </div>
    );
  }

  if (!schedule) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">公開されたシフトがありません。</p>
      </div>
    );
  }

  const [calYear, calMonth] = month.split("-").map(Number);
  const daysInMonth = new Date(calYear, calMonth, 0).getDate();
  const holidayDates = new Set(holidays.map((h) => h.date));
  const allDates: string[] = [];
  for (let d = 1; d <= daysInMonth; d++) {
    allDates.push(`${calYear}-${String(calMonth).padStart(2, "0")}-${String(d).padStart(2, "0")}`);
  }

  const assignmentMap: Record<string, ShiftAssignment> = {};
  for (const a of assignments) {
    assignmentMap[`${a.employee_id}_${a.date}`] = a;
  }

  const getSummary = (dateStr: string, jtId: number) =>
    assignments.filter((a) => a.date === dateStr && a.job_type_id === jtId).reduce((s, a) => s + a.headcount_value, 0);
  const getDailyTotal = (dateStr: string) =>
    assignments.filter((a) => a.date === dateStr && a.work_type !== "off").reduce((s, a) => s + a.headcount_value, 0);
  const getStaffTotal = (empId: number) =>
    assignments.filter((a) => a.employee_id === empId && a.work_type !== "off").reduce((s, a) => s + a.headcount_value, 0);

  const dowNames = ["日", "月", "火", "水", "木", "金", "土"];

  return (
    <div className="p-6 max-w-full">
      <div className="flex items-center gap-3 mb-6">
        <CalendarCheck className="h-6 w-6 text-primary" />
        <h1 className="text-2xl font-bold">
          シフト表 — {calYear}年{calMonth}月
        </h1>
        <Badge variant={schedule.status === "published" ? "success" : schedule.status === "confirmed" ? "default" : "secondary"}>
          {schedule.status === "published" ? "公開中" : schedule.status === "confirmed" ? "確定" : "プレビュー"}
        </Badge>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="overflow-x-auto">
            <table className="text-xs border-collapse w-full">
              <thead>
                <tr>
                  <th className="sticky left-0 bg-card z-10 px-2 py-1 border text-left min-w-[80px]">スタッフ</th>
                  {allDates.map((d) => {
                    const day = parseInt(d.split("-")[2]);
                    const dow = new Date(d).getDay();
                    const isNW = dow === 0 || dow === 6 || holidayDates.has(d);
                    return (
                      <th key={d} className={`px-1 py-1 border text-center min-w-[36px] ${isNW ? "bg-gray-100" : ""}`}>
                        <div>{day}</div>
                        <div className={`text-[10px] ${dow === 0 ? "text-red-500" : dow === 6 ? "text-blue-500" : ""}`}>
                          {dowNames[dow]}
                        </div>
                      </th>
                    );
                  })}
                  <th className="px-2 py-1 border text-center min-w-[40px] bg-muted/50">合計</th>
                </tr>
              </thead>
              <tbody>
                {employees.map((emp) => (
                  <tr key={emp.id}>
                    <td className="sticky left-0 bg-card z-10 px-2 py-1 border font-medium">{emp.name}</td>
                    {allDates.map((d) => {
                      const a = assignmentMap[`${emp.id}_${d}`];
                      const dow = new Date(d).getDay();
                      const isNW = dow === 0 || dow === 6 || holidayDates.has(d);
                      return (
                        <td
                          key={d}
                          className={`px-1 py-1 border text-center ${isNW ? "bg-gray-100" : ""}`}
                          style={a?.job_type_color && a.work_type !== "off" ? { backgroundColor: a.job_type_color + "30" } : {}}
                        >
                          {a?.work_type === "off" ? null : (
                            <span style={{ color: a?.job_type_color || undefined }} className="font-bold text-[11px]">
                              {a?.job_type_name?.charAt(0) || ""}
                              {a?.work_type === "morning_half" && <span className="text-[8px] font-normal opacity-70">前</span>}
                              {a?.work_type === "afternoon_half" && <span className="text-[8px] font-normal opacity-70">後</span>}
                            </span>
                          )}
                        </td>
                      );
                    })}
                    <td className="px-1 py-1 border text-center font-bold bg-muted/50">
                      {getStaffTotal(emp.id) || ""}
                    </td>
                  </tr>
                ))}
                {jobTypes.map((jt) => (
                  <tr key={`summary-${jt.id}`} className="bg-muted/30">
                    <td className="sticky left-0 bg-muted/30 z-10 px-2 py-1 border text-[10px] font-medium" style={{ color: jt.color || undefined }}>
                      {jt.name}
                    </td>
                    {allDates.map((d) => (
                      <td key={d} className="px-1 py-1 border text-center text-[10px] bg-muted/30">
                        {getSummary(d, jt.id) || ""}
                      </td>
                    ))}
                    <td className="px-1 py-1 border bg-muted/30" />
                  </tr>
                ))}
                <tr className="bg-muted/60 font-bold">
                  <td className="sticky left-0 bg-muted/60 z-10 px-2 py-1 border text-[10px]">日合計</td>
                  {allDates.map((d) => {
                    const dow = new Date(d).getDay();
                    const isNW = dow === 0 || dow === 6 || holidayDates.has(d);
                    return (
                      <td key={d} className="px-1 py-1 border text-center text-[10px] bg-muted/60">
                        {isNW ? "" : getDailyTotal(d) || ""}
                      </td>
                    );
                  })}
                  <td className="px-1 py-1 border bg-muted/60" />
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function SharePage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">読み込み中...</p>
      </div>
    }>
      <SharePageContent />
    </Suspense>
  );
}
