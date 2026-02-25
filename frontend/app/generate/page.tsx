"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Wand2, RefreshCw, Check, X, AlertTriangle, Loader2 } from "lucide-react";
import {
  getEmployees, getRequestStatus, getRequirements, getJobTypes,
  getSchedules, generateSchedule, getAssignments, getRequests, nlpModify, approveNlpLog, rejectNlpLog,
  type Employee, type JobType, type ShiftAssignment, type ShiftRequest, type NlpModifyResult,
} from "@/lib/api";

export default function GeneratePage() {
  const today = new Date();
  const defaultMonth = `${today.getFullYear()}-${String(today.getMonth() + 2).padStart(2, "0")}`;
  const [month, setMonth] = useState(defaultMonth);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [jobTypes, setJobTypes] = useState<JobType[]>([]);
  const [reqStatusCount, setReqStatusCount] = useState({ total: 0, done: 0 });
  const [reqDaysCount, setReqDaysCount] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [scheduleId, setScheduleId] = useState<number | null>(null);
  const [assignments, setAssignments] = useState<ShiftAssignment[]>([]);
  const [violations, setViolations] = useState<string[]>([]);
  const [nlpText, setNlpText] = useState("");
  const [nlpResult, setNlpResult] = useState<NlpModifyResult | null>(null);
  const [nlpLoading, setNlpLoading] = useState(false);
  const [error, setError] = useState("");
  const [requestedDaysOff, setRequestedDaysOff] = useState<Record<number, Set<string>>>({}); // empId -> Set<date>

  const load = async () => {
    const [emps, jts, statuses, reqs, schedules, shiftRequests] = await Promise.all([
      getEmployees(),
      getJobTypes(),
      getRequestStatus(month),
      getRequirements(month),
      getSchedules(month),
      getRequests(month),
    ]);
    setEmployees(emps);
    setJobTypes(jts);
    setReqStatusCount({ total: statuses.length, done: statuses.filter((s) => s.has_request).length });
    setReqDaysCount(new Set(reqs.map((r) => r.date)).size);

    // 希望休の日付をマッピング（半日休の期間情報を保持）
    const daysOffMap: Record<number, Set<string>> = {};
    for (const sr of shiftRequests) {
      const dates = new Set<string>();
      for (const d of sr.details) {
        dates.add(d.date);
      }
      daysOffMap[sr.employee_id] = dates;
    }
    setRequestedDaysOff(daysOffMap);

    if (schedules.length > 0) {
      const latest = schedules[0];
      setScheduleId(latest.id);
      const asn = await getAssignments(latest.id);
      setAssignments(asn);
    }
  };

  useEffect(() => {
    load();
  }, [month]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError("");
    setViolations([]);
    try {
      const result = await generateSchedule(month);
      setScheduleId(result.schedule_id);
      setViolations(result.violations);
      const asn = await getAssignments(result.schedule_id);
      setAssignments(asn);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "生成に失敗しました");
    } finally {
      setGenerating(false);
    }
  };

  const handleNlpModify = async () => {
    if (!scheduleId || !nlpText.trim()) return;
    setNlpLoading(true);
    setError("");
    try {
      const result = await nlpModify(scheduleId, nlpText);
      setNlpResult(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "修正に失敗しました");
    } finally {
      setNlpLoading(false);
    }
  };

  const handleApproveNlp = async () => {
    if (!nlpResult) return;
    await approveNlpLog(nlpResult.log_id);
    setScheduleId(nlpResult.new_schedule_id);
    const asn = await getAssignments(nlpResult.new_schedule_id);
    setAssignments(asn);
    setNlpResult(null);
    setNlpText("");
  };

  const handleRejectNlp = async () => {
    if (!nlpResult) return;
    await rejectNlpLog(nlpResult.log_id);
    setNlpResult(null);
  };

  const [calYear, calMonth] = month.split("-").map(Number);
  const daysInMonth = new Date(calYear, calMonth, 0).getDate();
  const allDates: string[] = [];
  for (let d = 1; d <= daysInMonth; d++) {
    allDates.push(
      `${calYear}-${String(calMonth).padStart(2, "0")}-${String(d).padStart(2, "0")}`
    );
  }

  const assignmentMap: Record<string, ShiftAssignment> = {};
  for (const a of assignments) {
    assignmentMap[`${a.employee_id}_${a.date}`] = a;
  }

  const dowNames = ["日", "月", "火", "水", "木", "金", "土"];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">シフト自動生成</h1>

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
          <CardTitle className="text-lg">事前チェック</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex gap-4">
            <Badge variant="secondary">登録スタッフ: {employees.length}名</Badge>
            <Badge
              variant={
                reqStatusCount.done === reqStatusCount.total ? "success" : "warning"
              }
            >
              希望入力済: {reqStatusCount.done}/{reqStatusCount.total}名
            </Badge>
            <Badge variant={reqDaysCount > 0 ? "success" : "warning"}>
              必要人数設定: {reqDaysCount}日
            </Badge>
          </div>
          <div className="flex gap-2 pt-4">
            <Button onClick={handleGenerate} disabled={generating} size="lg">
              {generating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  生成中...
                </>
              ) : (
                <>
                  <Wand2 className="mr-2 h-4 w-4" />
                  自動生成
                </>
              )}
            </Button>
            {scheduleId && (
              <Button onClick={handleGenerate} variant="outline" disabled={generating}>
                <RefreshCw className="mr-2 h-4 w-4" />
                再生成
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              {error}
            </p>
          </CardContent>
        </Card>
      )}

      {violations.length > 0 && (
        <Card className="border-yellow-500">
          <CardHeader>
            <CardTitle className="text-lg text-yellow-600">制約違反</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc pl-5 space-y-1 text-sm text-yellow-700">
              {violations.map((v, i) => (
                <li key={i}>{v}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {assignments.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">プレビュー</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="text-xs border-collapse">
                <thead>
                  <tr>
                    <th className="sticky left-0 bg-card z-10 px-2 py-1 border text-left min-w-[80px]">
                      スタッフ
                    </th>
                    {allDates.map((d) => {
                      const day = parseInt(d.split("-")[2]);
                      const dow = new Date(d).getDay();
                      return (
                        <th
                          key={d}
                          className={`px-1 py-1 border text-center min-w-[32px] ${
                            dow === 0 || dow === 6 ? "bg-gray-100" : ""
                          }`}
                        >
                          <div>{day}</div>
                          <div
                            className={`text-[10px] ${
                              dow === 0
                                ? "text-red-500"
                                : dow === 6
                                  ? "text-blue-500"
                                  : ""
                            }`}
                          >
                            {dowNames[dow]}
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {employees.map((emp) => (
                    <tr key={emp.id}>
                      <td className="sticky left-0 bg-card z-10 px-2 py-1 border font-medium">
                        {emp.name}
                      </td>
                      {allDates.map((d) => {
                        const a = assignmentMap[`${emp.id}_${d}`];
                        const isChanged = nlpResult?.changes.some(
                          (c) => c.employee_id === emp.id && c.date === d
                        );
                        const dow = new Date(d).getDay();
                        const isWeekend = dow === 0 || dow === 6;
                        const isOff = a?.work_type === "off";
                        const isRequested = requestedDaysOff[emp.id]?.has(d);
                        return (
                          <td
                            key={d}
                            className={`px-1 py-1 border text-center ${
                              isChanged ? "ring-2 ring-yellow-400" : ""
                            }`}
                            style={
                              a?.job_type_color && !isOff
                                ? { backgroundColor: a.job_type_color + "40" }
                                : isOff && !isWeekend && isRequested
                                  ? { backgroundColor: "#DBEAFE" }
                                  : isOff && !isWeekend && !isRequested
                                    ? { backgroundColor: "#FEF3C7" }
                                    : {}
                            }
                          >
                            {isOff ? (
                              isWeekend ? null : (
                                <span className={isRequested ? "text-blue-600 font-bold text-[10px]" : "text-amber-600 text-[10px]"}>
                                  {isRequested ? "希休" : "調休"}
                                </span>
                              )
                            ) : (
                              <span className="text-[10px]">
                                {a?.job_type_name?.charAt(0) || ""}
                                {a?.work_type === "morning_half" && <span className="text-[8px] text-muted-foreground">前</span>}
                                {a?.work_type === "afternoon_half" && <span className="text-[8px] text-muted-foreground">後</span>}
                              </span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                  {/* 職種別人数 */}
                  {jobTypes.map((jt) => (
                    <tr key={`summary-${jt.id}`} className="bg-muted/30">
                      <td className="sticky left-0 bg-muted/30 z-10 px-2 py-1 border text-[10px] font-medium" style={{ color: jt.color || undefined }}>
                        {jt.name}
                      </td>
                      {allDates.map((d) => {
                        const count = assignments.filter((a) => a.date === d && a.job_type_id === jt.id).reduce((s, a) => s + a.headcount_value, 0);
                        return (
                          <td key={d} className="px-1 py-1 border text-center text-[10px]">
                            {count || ""}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                  {/* 日合計 */}
                  <tr className="bg-muted/60 font-bold">
                    <td className="sticky left-0 bg-muted/60 z-10 px-2 py-1 border text-[10px]">合計</td>
                    {allDates.map((d) => {
                      const total = assignments.filter((a) => a.date === d && a.work_type !== "off").reduce((s, a) => s + a.headcount_value, 0);
                      return (
                        <td key={d} className="px-1 py-1 border text-center text-[10px]">
                          {total || ""}
                        </td>
                      );
                    })}
                  </tr>
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {scheduleId && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">自然言語でシフト修正</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              placeholder="例: スタッフAのデータをもっと増やして。スタッフBのその他を減らしてください"
              value={nlpText}
              onChange={(e) => setNlpText(e.target.value)}
            />
            <Button
              onClick={handleNlpModify}
              disabled={nlpLoading || !nlpText.trim()}
            >
              {nlpLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  解析中...
                </>
              ) : (
                "修正を適用"
              )}
            </Button>

            {nlpResult && (
              <div className="space-y-3 pt-3 border-t">
                <h4 className="font-medium">
                  変更内容（{nlpResult.changes.length}件）
                </h4>
                <div className="max-h-40 overflow-y-auto text-sm space-y-1">
                  {nlpResult.changes.map((c, i) => (
                    <div key={i} className="flex gap-2">
                      <span className="font-medium">{c.employee_name}</span>
                      <span>{c.date}</span>
                      <span className="text-red-500">{c.old_job_type}</span>
                      <span>→</span>
                      <span className="text-green-500">{c.new_job_type}</span>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2">
                  <Button onClick={handleApproveNlp} variant="default">
                    <Check className="mr-2 h-4 w-4" />
                    承認
                  </Button>
                  <Button onClick={handleRejectNlp} variant="outline">
                    <X className="mr-2 h-4 w-4" />
                    却下
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
