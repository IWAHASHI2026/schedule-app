"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Save } from "lucide-react";
import {
  getEmployees, getRequestStatus, getHolidays, upsertRequest,
  type Employee, type RequestStatus, type Holiday,
} from "@/lib/api";

export default function RequestsPage() {
  const today = new Date();
  const defaultMonth = `${today.getFullYear()}-${String(today.getMonth() + 2).padStart(2, "0")}`;
  const [month, setMonth] = useState(defaultMonth);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [statuses, setStatuses] = useState<RequestStatus[]>([]);
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [selectedEmpId, setSelectedEmpId] = useState<string>("");
  const [selectedDaysOff, setSelectedDaysOff] = useState<Set<string>>(new Set());
  const [workDays, setWorkDays] = useState<string>("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const load = async () => {
    const [emps, sts, hols] = await Promise.all([
      getEmployees(),
      getRequestStatus(month),
      getHolidays(parseInt(month.split("-")[0])),
    ]);
    setEmployees(emps);
    setStatuses(sts);
    setHolidays(hols);
  };

  useEffect(() => { load(); }, [month]);

  const loadEmployeeRequest = async (empId: string) => {
    setSelectedEmpId(empId);
    setSelectedDaysOff(new Set());
    setWorkDays("");
    setNote("");
    if (!empId) return;
    try {
      const { getEmployeeRequest } = await import("@/lib/api");
      const req = await getEmployeeRequest(parseInt(empId), month);
      const keys = new Set<string>();
      for (const d of req.details) {
        if (d.period === "am" || d.period === "pm") {
          keys.add(`${d.date}_${d.period}`);
        } else {
          keys.add(`${d.date}_am`);
          keys.add(`${d.date}_pm`);
        }
      }
      setSelectedDaysOff(keys);
      setWorkDays(req.requested_work_days || "");
      setNote(req.note || "");
    } catch {
      // No existing request
    }
  };

  const handleSave = async () => {
    if (!selectedEmpId) return;
    setSaving(true);
    try {
      await upsertRequest({
        employee_id: parseInt(selectedEmpId),
        target_month: month,
        requested_work_days: workDays && workDays !== "__none__" ? workDays : null,
        note: note || null,
        days_off: (() => {
          const dateMap = new Map<string, Set<string>>();
          for (const key of selectedDaysOff) {
            const [dateStr, period] = key.split("_");
            if (!dateMap.has(dateStr)) dateMap.set(dateStr, new Set());
            dateMap.get(dateStr)!.add(period);
          }
          const result: { date: string; period: string }[] = [];
          for (const [dateStr, periods] of dateMap) {
            if (periods.has("am") && periods.has("pm")) {
              result.push({ date: dateStr, period: "all_day" });
            } else {
              for (const p of periods) {
                result.push({ date: dateStr, period: p });
              }
            }
          }
          return result;
        })(),
      });
      load();
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } finally {
      setSaving(false);
    }
  };

  // Calendar generation
  const [calYear, calMonth] = month.split("-").map(Number);
  const daysInMonth = new Date(calYear, calMonth, 0).getDate();
  const firstDow = new Date(calYear, calMonth - 1, 1).getDay();
  const holidayDates = new Set(holidays.map((h) => h.date));

  const togglePeriod = (dateStr: string, period: "am" | "pm") => {
    setSelectedDaysOff((prev) => {
      const next = new Set(prev);
      const key = `${dateStr}_${period}`;
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const calendarWeeks: (number | null)[][] = [];
  let week: (number | null)[] = new Array(firstDow).fill(null);
  for (let d = 1; d <= daysInMonth; d++) {
    week.push(d);
    if (week.length === 7) {
      calendarWeeks.push(week);
      week = [];
    }
  }
  if (week.length > 0) {
    while (week.length < 7) week.push(null);
    calendarWeeks.push(week);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">希望入力</h1>

      <div className="flex gap-4 items-end">
        <div>
          <Label>対象月</Label>
          <Input
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="mt-1 w-44"
          />
        </div>
        <div>
          <Label>スタッフ選択</Label>
          <Select value={selectedEmpId} onValueChange={loadEmployeeRequest}>
            <SelectTrigger className="mt-1 w-48">
              <SelectValue placeholder="選択してください" />
            </SelectTrigger>
            <SelectContent>
              {employees.map((emp) => (
                <SelectItem key={emp.id} value={emp.id.toString()}>
                  {emp.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {selectedEmpId && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">希望休日（クリックで選択）</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="select-none">
                <div className="grid grid-cols-7 gap-1 text-center text-sm font-medium text-muted-foreground mb-2">
                  {["日", "月", "火", "水", "木", "金", "土"].map((d) => (
                    <div key={d}>{d}</div>
                  ))}
                </div>
                {calendarWeeks.map((week, wi) => (
                  <div key={wi} className="grid grid-cols-7 gap-1">
                    {week.map((day, di) => {
                      if (day === null) return <div key={di} />;
                      const dateStr = `${calYear}-${String(calMonth).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                      const dow = new Date(calYear, calMonth - 1, day).getDay();
                      const isWeekend = dow === 0 || dow === 6;
                      const isHoliday = holidayDates.has(dateStr);
                      const isNonWorking = isWeekend || isHoliday;
                      const amSelected = selectedDaysOff.has(`${dateStr}_am`);
                      const pmSelected = selectedDaysOff.has(`${dateStr}_pm`);

                      return (
                        <div key={di} className={`rounded text-sm overflow-hidden border ${isNonWorking ? "bg-gray-100 text-gray-400" : "border-gray-200"}`}>
                          <div className="text-center text-xs py-0.5 font-medium">{day}</div>
                          {isNonWorking ? (
                            <div className="h-8" />
                          ) : (
                            <div className="flex flex-col">
                              <button
                                onClick={() => togglePeriod(dateStr, "am")}
                                className={`h-4 text-[10px] leading-none transition-colors ${amSelected ? "bg-blue-500 text-white" : "hover:bg-blue-100"}`}
                              >
                                午前
                              </button>
                              <button
                                onClick={() => togglePeriod(dateStr, "pm")}
                                className={`h-4 text-[10px] leading-none transition-colors ${pmSelected ? "bg-blue-500 text-white" : "hover:bg-blue-100"}`}
                              >
                                午後
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                選択中の希望休日: {selectedDaysOff.size}件（午前/午後）
              </p>
            </CardContent>
          </Card>

          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">希望情報</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label>希望出勤日数</Label>
                  <Select value={workDays} onValueChange={setWorkDays}>
                    <SelectTrigger className="mt-1 w-48">
                      <SelectValue placeholder="選択してください" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">未選択</SelectItem>
                      {Array.from({ length: 23 }, (_, i) => i + 1).map((n) => (
                        <SelectItem key={n} value={String(n)}>
                          {n}日
                        </SelectItem>
                      ))}
                      <SelectItem value="max">なるべく多く</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>備考</Label>
                  <Textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    className="mt-1"
                    placeholder="自由記述"
                  />
                </div>
                <Button onClick={handleSave} disabled={saving} className="w-full">
                  <Save className="mr-2 h-4 w-4" />
                  {saving ? "保存中..." : "保存"}
                </Button>
                {saved && (
                  <p className="text-green-600 text-sm font-medium text-center mt-2">保存しました</p>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">入力状況一覧</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {statuses.map((s) => (
              <Badge key={s.employee_id} variant={s.has_request ? "success" : "secondary"}>
                {s.employee_name}: {s.has_request ? "入力済" : "未入力"}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
