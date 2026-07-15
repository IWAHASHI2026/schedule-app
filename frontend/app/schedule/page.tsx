"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, Globe, Save } from "lucide-react";
import {
  getEmployees, getJobTypes, getSchedules, getAssignments, getHolidays, getRequests,
  updateAssignments, updateScheduleStatus, getJobTypeAbbr,
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
  const [requestedDaysOff, setRequestedDaysOff] = useState<Record<number, Set<string>>>({});
  const [pendingChanges, setPendingChanges] = useState<Record<string, { employee_id: number; date: string; job_type_id: number | null; work_type: string }>>({});
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const [emps, jts, scheds, hols, shiftRequests] = await Promise.all([
      getEmployees(),
      getJobTypes(),
      getSchedules(month),
      getHolidays(parseInt(month.split("-")[0])),
      getRequests(month),
    ]);
    setEmployees(emps);
    setJobTypes(jts);
    setHolidays(hols);

    // 希望休の日付をマッピング
    const daysOffMap: Record<number, Set<string>> = {};
    for (const sr of shiftRequests) {
      const dates = new Set<string>();
      for (const d of sr.details) {
        dates.add(d.date);
      }
      daysOffMap[sr.employee_id] = dates;
    }
    setRequestedDaysOff(daysOffMap);

    if (scheds.length > 0) {
      setSchedule(scheds[0]);
      const asn = await getAssignments(scheds[0].id);
      setAssignments(asn);
    } else {
      setSchedule(null);
      setAssignments([]);
    }
  };

  useEffect(() => { load(); setPendingChanges({}); }, [month]);

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
    if (dow === 0 || dow === 6 || holidayDates.has(dateStr)) {
      // 生成後に休業日を追加した場合に残っている勤務割当だけは手動で外せるようにする
      const a = assignmentMap[`${empId}_${dateStr}`];
      const hasActiveWork =
        a && a.work_type !== "off" && a.work_type !== "requested_off" && a.work_type !== "adjusted_off";
      if (!hasActiveWork) return;
    }
    setEditCell({ empId, date: dateStr });
  };

  const handleAssign = (jtId: number | null, workType?: string) => {
    if (!editCell || !schedule) return;
    const wt = jtId ? (workType || "full") : (workType || "adjusted_off");
    const key = `${editCell.empId}_${editCell.date}`;

    // Store pending change
    setPendingChanges((prev) => ({
      ...prev,
      [key]: { employee_id: editCell.empId, date: editCell.date, job_type_id: jtId, work_type: wt },
    }));

    // Update local assignments for instant UI feedback
    const jt = jtId ? jobTypes.find((j) => j.id === jtId) : null;
    const isOff = !jtId;
    const hv = isOff ? 0 : (wt === "morning_half" || wt === "afternoon_half" ? 0.5 : 1.0);
    setAssignments((prev) => {
      const idx = prev.findIndex((a) => a.employee_id === editCell.empId && a.date === editCell.date);
      const updated: ShiftAssignment = {
        id: idx >= 0 ? prev[idx].id : 0,
        schedule_id: schedule.id,
        employee_id: editCell.empId,
        employee_name: prev[idx]?.employee_name || "",
        date: editCell.date,
        job_type_id: jtId,
        job_type_name: jt?.name || null,
        job_type_color: jt?.color || null,
        work_type: wt,
        headcount_value: hv,
      };
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = updated;
        return next;
      }
      return [...prev, updated];
    });
    setEditCell(null);
  };

  const handleSave = async () => {
    if (!schedule || Object.keys(pendingChanges).length === 0) return;
    setSaving(true);
    try {
      await updateAssignments(schedule.id, Object.values(pendingChanges));
      setPendingChanges({});
      const asn = await getAssignments(schedule.id);
      setAssignments(asn);
    } finally {
      setSaving(false);
    }
  };

  const hasPendingChanges = Object.keys(pendingChanges).length > 0;

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
  const offTypes = new Set(["off", "requested_off", "adjusted_off"]);
  const getDailyTotal = (dateStr: string) => {
    return assignments
      .filter((a) => a.date === dateStr && !offTypes.has(a.work_type))
      .reduce((sum, a) => sum + a.headcount_value, 0);
  };

  // Staff total work days
  const getStaffTotal = (empId: number) => {
    return assignments
      .filter((a) => a.employee_id === empId && !offTypes.has(a.work_type))
      .reduce((sum, a) => sum + a.headcount_value, 0);
  };

  const dowNames = ["日", "月", "火", "水", "木", "金", "土"];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">シフト表</h1>
        {schedule && (
          <div className="flex items-center gap-2">
            {hasPendingChanges && (
              <Button onClick={handleSave} size="sm" variant="default" disabled={saving}>
                <Save className="mr-2 h-4 w-4" />{saving ? "保存中..." : `保存（${Object.keys(pendingChanges).length}件）`}
              </Button>
            )}
            <Badge variant={
              schedule.status === "published" ? "success" :
              schedule.status === "confirmed" ? "default" : "secondary"
            }>
              {schedule.status === "published" ? "公開中" :
               schedule.status === "confirmed" ? "確定" :
               schedule.status === "preview" ? "プレビュー" : "下書き"}
            </Badge>
            {(schedule.status === "draft" || schedule.status === "preview") && (
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
                        const isPending = `${emp.id}_${d}` in pendingChanges;
                        const isOff = a?.work_type === "off" || a?.work_type === "requested_off" || a?.work_type === "adjusted_off";
                        const isRequested = a?.work_type === "requested_off" || (a?.work_type === "off" && requestedDaysOff[emp.id]?.has(d));
                        return (
                          <td
                            key={d}
                            onClick={() => handleCellClick(emp.id, d)}
                            className={`px-1 py-1 border text-center cursor-pointer hover:ring-2 hover:ring-blue-300 ${isNW ? "bg-gray-100" : ""} ${isEditing ? "ring-2 ring-blue-500" : ""} ${isPending ? "ring-2 ring-orange-400" : ""}`}
                            style={
                              a?.job_type_color && !isOff
                                ? { backgroundColor: a.job_type_color + "30" }
                                : isOff && !isNW && isRequested
                                  ? { backgroundColor: "#F3E8FF" }
                                  : isOff && !isNW && !isRequested
                                    ? { backgroundColor: "#F1F5F9" }
                                    : {}
                            }
                          >
                            {isOff ? (
                              isNW ? null : (
                                <span className={isRequested ? "text-purple-600 font-bold text-[10px]" : "text-slate-500 text-[10px]"}>
                                  {isRequested ? "希休" : "調休"}
                                </span>
                              )
                            ) : (
                              <span style={{ color: a?.job_type_color || undefined }} className="font-bold text-[11px]">
                                {getJobTypeAbbr(a?.job_type_name)}
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
                {(() => {
                  const sonota = jobTypes.find((jt) => jt.name === "その他");
                  if (!sonota) return null;
                  return (
                    <>
                      <Button key="sonota-am" size="sm" variant="outline" onClick={() => handleAssign(sonota.id, "morning_half")}
                        style={{ borderColor: sonota.color || undefined, color: sonota.color || undefined }}>
                        その他 午前
                      </Button>
                      <Button key="sonota-pm" size="sm" variant="outline" onClick={() => handleAssign(sonota.id, "afternoon_half")}
                        style={{ borderColor: sonota.color || undefined, color: sonota.color || undefined }}>
                        その他 午後
                      </Button>
                    </>
                  );
                })()}
                <Button size="sm" variant="ghost" onClick={() => handleAssign(null, "requested_off")}
                  style={{ color: "#7C3AED" }}>希望休</Button>
                <Button size="sm" variant="ghost" onClick={() => handleAssign(null, "adjusted_off")}
                  style={{ color: "#64748B" }}>調整休</Button>
                <Button size="sm" variant="ghost" onClick={() => setEditCell(null)}>キャンセル</Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
