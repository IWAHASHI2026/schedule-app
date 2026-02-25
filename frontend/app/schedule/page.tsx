"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, Globe } from "lucide-react";
import {
  getEmployees, getJobTypes, getSchedules, getAssignments, getHolidays,
  updateAssignments, updateScheduleStatus,
  type Employee, type JobType, type Schedule, type ShiftAssignment, type Holiday,
} from "@/lib/api";

export default function SchedulePage() {
  const today = new Date();
  const defaultMonth = `${today.getFullYear()}-${String(today.getMonth() + 2).padStart(2, "0")}`;
  const [month, setMonth] = useState(defaultMonth);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [jobTypes, setJobTypes] = useState<JobType[]>([]);
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [assignments, setAssignments] = useState<ShiftAssignment[]>([]);
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [editCell, setEditCell] = useState<{ empId: number; date: string } | null>(null);

  const load = async () => {
    const [emps, jts, scheds, hols] = await Promise.all([
      getEmployees(),
      getJobTypes(),
      getSchedules(month),
      getHolidays(parseInt(month.split("-")[0])),
    ]);
    setEmployees(emps);
    setJobTypes(jts);
    setHolidays(hols);
    if (scheds.length > 0) {
      setSchedule(scheds[0]);
      const asn = await getAssignments(scheds[0].id);
      setAssignments(asn);
    } else {
      setSchedule(null);
      setAssignments([]);
    }
  };

  useEffect(() => { load(); }, [month]);

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

  const handleCellClick = (empId: number, dateStr: string) => {
    const dow = new Date(dateStr).getDay();
    if (dow === 0 || dow === 6 || holidayDates.has(dateStr)) return;
    setEditCell({ empId, date: dateStr });
  };

  const handleAssign = async (jtId: number | null) => {
    if (!editCell || !schedule) return;
    await updateAssignments(schedule.id, [{
      employee_id: editCell.empId,
      date: editCell.date,
      job_type_id: jtId,
      work_type: jtId ? "full" : "off",
    }]);
    setEditCell(null);
    const asn = await getAssignments(schedule.id);
    setAssignments(asn);
  };

  const handleStatus = async (status: string) => {
    if (!schedule) return;
    await updateScheduleStatus(schedule.id, status);
    load();
  };

  // Summary per date per job type
  const getSummary = (dateStr: string, jtId: number) => {
    return assignments
      .filter((a) => a.date === dateStr && a.job_type_id === jtId)
      .reduce((sum, a) => sum + a.headcount_value, 0);
  };

  // Daily total (all job types)
  const getDailyTotal = (dateStr: string) => {
    return assignments
      .filter((a) => a.date === dateStr && a.work_type !== "off")
      .reduce((sum, a) => sum + a.headcount_value, 0);
  };

  // Staff total work days
  const getStaffTotal = (empId: number) => {
    return assignments
      .filter((a) => a.employee_id === empId && a.work_type !== "off")
      .reduce((sum, a) => sum + a.headcount_value, 0);
  };

  const dowNames = ["日", "月", "火", "水", "木", "金", "土"];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">シフト表</h1>
        {schedule && (
          <div className="flex items-center gap-2">
            <Badge variant={
              schedule.status === "published" ? "success" :
              schedule.status === "confirmed" ? "default" : "secondary"
            }>
              {schedule.status === "published" ? "公開中" :
               schedule.status === "confirmed" ? "確定" :
               schedule.status === "preview" ? "プレビュー" : "下書き"}
            </Badge>
            {schedule.status === "preview" && (
              <Button onClick={() => handleStatus("confirmed")} size="sm">
                <CheckCircle className="mr-2 h-4 w-4" />確定
              </Button>
            )}
            {schedule.status === "confirmed" && (
              <Button onClick={() => handleStatus("published")} size="sm">
                <Globe className="mr-2 h-4 w-4" />公開
              </Button>
            )}
          </div>
        )}
      </div>

      <div>
        <Label>対象月</Label>
        <Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="mt-1 w-44" />
      </div>

      {!schedule ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            シフトが生成されていません。「シフト自動生成」画面から生成してください。
          </CardContent>
        </Card>
      ) : (
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
                        const isEditing = editCell?.empId === emp.id && editCell?.date === d;
                        return (
                          <td
                            key={d}
                            onClick={() => handleCellClick(emp.id, d)}
                            className={`px-1 py-1 border text-center cursor-pointer hover:ring-2 hover:ring-blue-300 ${isNW ? "bg-gray-100" : ""} ${isEditing ? "ring-2 ring-blue-500" : ""}`}
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
                  {/* Summary rows */}
                  {jobTypes.map((jt) => (
                    <tr key={`summary-${jt.id}`} className="bg-muted/30">
                      <td className="sticky left-0 bg-muted/30 z-10 px-2 py-1 border text-[10px] font-medium" style={{ color: jt.color || undefined }}>
                        {jt.name}
                      </td>
                      {allDates.map((d) => (
                        <td key={d} className="px-1 py-1 border text-center text-[10px]">
                          {getSummary(d, jt.id) || ""}
                        </td>
                      ))}
                      <td className="px-1 py-1 border" />
                    </tr>
                  ))}
                  <tr className="bg-muted/60 font-bold">
                    <td className="sticky left-0 bg-muted/60 z-10 px-2 py-1 border text-[10px]">日合計</td>
                    {allDates.map((d) => {
                      const dow = new Date(d).getDay();
                      const isNW = dow === 0 || dow === 6 || holidayDates.has(d);
                      return (
                        <td key={d} className="px-1 py-1 border text-center text-[10px]">
                          {isNW ? "" : getDailyTotal(d) || ""}
                        </td>
                      );
                    })}
                    <td className="px-1 py-1 border" />
                  </tr>
                </tbody>
              </table>
            </div>

            {editCell && (
              <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-card border rounded-lg shadow-lg p-4 z-50 flex gap-2 items-center">
                <span className="text-sm mr-2">割り当て:</span>
                {jobTypes.map((jt) => (
                  <Button key={jt.id} size="sm" variant="outline" onClick={() => handleAssign(jt.id)}
                    style={{ borderColor: jt.color || undefined, color: jt.color || undefined }}>
                    {jt.name}
                  </Button>
                ))}
                <Button size="sm" variant="ghost" onClick={() => handleAssign(null)}>休み</Button>
                <Button size="sm" variant="ghost" onClick={() => setEditCell(null)}>キャンセル</Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
