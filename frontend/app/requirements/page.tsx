"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Save, Copy } from "lucide-react";
import {
  getJobTypes, getRequirements, upsertRequirements, applyTemplate, getHolidays,
  type JobType, type DailyRequirement, type Holiday,
} from "@/lib/api";

export default function RequirementsPage() {
  const today = new Date();
  const defaultMonth = `${today.getFullYear()}-${String(today.getMonth() + 2).padStart(2, "0")}`;
  const [month, setMonth] = useState(defaultMonth);
  const [jobTypes, setJobTypes] = useState<JobType[]>([]);
  const [requirements, setRequirements] = useState<DailyRequirement[]>([]);
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [values, setValues] = useState<Record<string, number>>({});
  const [templateValues, setTemplateValues] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);
  const load = async () => {
    const [jts, reqs, hols] = await Promise.all([
      getJobTypes(),
      getRequirements(month),
      getHolidays(parseInt(month.split("-")[0])),
    ]);
    setJobTypes(jts);
    setRequirements(reqs);
    setHolidays(hols);

    const vals: Record<string, number> = {};
    for (const r of reqs) {
      vals[`${r.date}_${r.job_type_id}`] = r.required_count;
    }
    setValues(vals);
  };

  useEffect(() => { load(); }, [month]);

  const [calYear, calMonth] = month.split("-").map(Number);
  const daysInMonth = new Date(calYear, calMonth, 0).getDate();
  const holidayDates = new Set(holidays.map((h) => h.date));
  const dates: { date: string; day: number; dow: number; isNonWorking: boolean }[] = [];
  for (let d = 1; d <= daysInMonth; d++) {
    const dt = new Date(calYear, calMonth - 1, d);
    const dateStr = `${calYear}-${String(calMonth).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    const dow = dt.getDay();
    dates.push({
      date: dateStr,
      day: d,
      dow,
      isNonWorking: dow === 0 || dow === 6 || holidayDates.has(dateStr),
    });
  }

  const dowNames = ["日", "月", "火", "水", "木", "金", "土"];

  const setValue = (dateStr: string, jtId: number, val: string) => {
    const num = val === "" ? 0 : parseFloat(val);
    setValues((prev) => ({ ...prev, [`${dateStr}_${jtId}`]: num }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const items = Object.entries(values)
        .filter(([, v]) => v > 0)
        .map(([key, v]) => {
          const [dateStr, jtId] = key.split("_");
          return { date: dateStr, job_type_id: parseInt(jtId), required_count: v };
        });
      await upsertRequirements(items);
      load();
    } finally {
      setSaving(false);
    }
  };

  const handleApplyTemplate = async () => {
    const weekdayReqs: Record<number, { job_type_id: number; required_count: number }[]> = {};
    for (const [key, val] of Object.entries(templateValues)) {
      if (val <= 0) continue;
      const [dowStr, jtIdStr] = key.split("_");
      const dow = parseInt(dowStr);
      // Convert JS getDay() style (1=Mon..5=Fri) to Python weekday() style (0=Mon..4=Fri)
      const pyDow = dow - 1;
      if (!weekdayReqs[pyDow]) weekdayReqs[pyDow] = [];
      weekdayReqs[pyDow].push({ job_type_id: parseInt(jtIdStr), required_count: val });
    }
    await applyTemplate({ month, weekday_requirements: weekdayReqs });
    load();
  };

  const getRowTotal = (dateStr: string) => {
    return jobTypes.reduce((sum, jt) => sum + (values[`${dateStr}_${jt.id}`] || 0), 0);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">日別必要人数設定</h1>

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
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">曜日テンプレート一括設定</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-2 px-2 text-left">曜日</th>
                  {jobTypes.map((jt) => (
                    <th key={jt.id} className="py-2 px-2 text-center">
                      <span className="inline-block h-2 w-2 rounded-full mr-1" style={{ backgroundColor: jt.color || "#ccc" }} />
                      {jt.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[1, 2, 3, 4, 5].map((dow) => (
                  <tr key={dow} className="border-b">
                    <td className="py-1 px-2 font-medium">{dowNames[dow]}</td>
                    {jobTypes.map((jt) => (
                      <td key={jt.id} className="py-1 px-2">
                        <Input
                          type="number"
                          min={0}
                          step={1}
                          className="w-20 h-8 text-center text-sm"
                          value={templateValues[`${dow}_${jt.id}`] || ""}
                          onChange={(e) =>
                            setTemplateValues((prev) => ({
                              ...prev,
                              [`${dow}_${jt.id}`]: parseFloat(e.target.value) || 0,
                            }))
                          }
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Button onClick={handleApplyTemplate} variant="secondary" className="mt-3">
            <Copy className="mr-2 h-4 w-4" />
            テンプレートを全営業日に適用
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg">日別必要人数</CardTitle>
          <Button onClick={handleSave} disabled={saving}>
            <Save className="mr-2 h-4 w-4" />
            {saving ? "保存中..." : "保存"}
          </Button>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="text-sm w-full">
              <thead>
                <tr className="border-b">
                  <th className="py-2 px-2 text-left sticky left-0 bg-card">日付</th>
                  <th className="py-2 px-2 text-left">曜日</th>
                  {jobTypes.map((jt) => (
                    <th key={jt.id} className="py-2 px-2 text-center">
                      <span className="inline-block h-2 w-2 rounded-full mr-1" style={{ backgroundColor: jt.color || "#ccc" }} />
                      {jt.name}
                    </th>
                  ))}
                  <th className="py-2 px-2 text-center">合計</th>
                </tr>
              </thead>
              <tbody>
                {dates.map(({ date: dateStr, day, dow, isNonWorking }) => (
                  <tr
                    key={dateStr}
                    className={`border-b ${isNonWorking ? "bg-gray-50 text-gray-400" : ""}`}
                  >
                    <td className="py-1 px-2 sticky left-0 bg-inherit">{day}</td>
                    <td className={`py-1 px-2 ${dow === 0 ? "text-red-500" : dow === 6 ? "text-blue-500" : ""}`}>
                      {dowNames[dow]}
                    </td>
                    {jobTypes.map((jt) => (
                      <td key={jt.id} className="py-1 px-2">
                        {isNonWorking ? (
                          <span className="text-gray-300">-</span>
                        ) : (
                          <Input
                            type="number"
                            min={0}
                            step={1}
                            className="w-20 h-8 text-center text-sm"
                            value={values[`${dateStr}_${jt.id}`] || ""}
                            onChange={(e) => setValue(dateStr, jt.id, e.target.value)}
                          />
                        )}
                      </td>
                    ))}
                    <td className="py-1 px-2 text-center font-medium">
                      {isNonWorking ? "-" : getRowTotal(dateStr)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
