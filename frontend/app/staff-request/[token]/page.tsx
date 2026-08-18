"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Send, CheckCircle } from "lucide-react";
import {
  getStaffPortalInfo, submitStaffRequest, getHolidays,
  type StaffPortalInfo, type Holiday,
} from "@/lib/api";

const defaultWorkDaysMap: Record<string, string> = {
  "部長": "max",
  "若生亜紀子": "max",
  "大野千絵美": "16",
  "和平映美": "max",
  "岡崎智恵子": "16",
  "川上朋子": "12",
  "植原ふみ代": "16",
  "尾崎廣子": "12",
  "酒向邦江": "12",
  "カンサ萌": "12",
  "秋山智子": "12",
  "石原圭子": "16",
  "工藤友里": "max",
  "近藤美佐子": "max",
  "竹下久美子": "12",
};

export default function StaffRequestPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const token = params.token as string;

  const today = new Date();
  const nextMonth = new Date(today.getFullYear(), today.getMonth() + 1, 1);
  const defaultMonth = `${nextMonth.getFullYear()}-${String(nextMonth.getMonth() + 1).padStart(2, "0")}`;
  const month = searchParams.get("month") || defaultMonth;

  const [info, setInfo] = useState<StaffPortalInfo | null>(null);
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedDaysOff, setSelectedDaysOff] = useState<Set<string>>(new Set());
  const [workDays, setWorkDays] = useState<string>("");
  const [weeklyLimit, setWeeklyLimit] = useState<string>("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Hide navigation sidebar
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
    (async () => {
      try {
        const [portalInfo, hols] = await Promise.all([
          getStaffPortalInfo(token, month),
          getHolidays(parseInt(month.split("-")[0])),
        ]);
        setInfo(portalInfo);
        setHolidays(hols);

        // Prefill from existing request
        if (portalInfo.existing_request) {
          const req = portalInfo.existing_request;
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
          setWorkDays(req.requested_work_days || defaultWorkDaysMap[portalInfo.employee_name] || "");
          setWeeklyLimit(req.weekly_work_day_limit != null ? String(req.weekly_work_day_limit) : "");
          setNote(req.note || "");
        } else {
          setWorkDays(defaultWorkDaysMap[portalInfo.employee_name] || "");
        }
      } catch {
        setError("無効なリンクです。管理者にお問い合わせください。");
      } finally {
        setLoading(false);
      }
    })();
  }, [token, month]);

  const handleSubmit = async () => {
    if (!info) return;
    setSaving(true);
    try {
      const dateMap = new Map<string, Set<string>>();
      for (const key of selectedDaysOff) {
        const [dateStr, period] = key.split("_");
        if (!dateMap.has(dateStr)) dateMap.set(dateStr, new Set());
        dateMap.get(dateStr)!.add(period);
      }
      const daysOff: { date: string; period: string }[] = [];
      for (const [dateStr, periods] of dateMap) {
        if (periods.has("am") && periods.has("pm")) {
          daysOff.push({ date: dateStr, period: "all_day" });
        } else {
          for (const p of periods) {
            daysOff.push({ date: dateStr, period: p });
          }
        }
      }

      await submitStaffRequest(token, {
        target_month: month,
        requested_work_days: workDays && workDays !== "__none__" ? workDays : null,
        weekly_work_day_limit: weeklyLimit && weeklyLimit !== "__none__" ? parseInt(weeklyLimit) : null,
        note: note || null,
        days_off: daysOff,
      });
      setSaved(true);
    } catch {
      alert("送信に失敗しました。もう一度お試しください。");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen p-4">
        <p className="text-muted-foreground">読み込み中...</p>
      </div>
    );
  }

  if (error || !info) {
    return (
      <div className="flex items-center justify-center min-h-screen p-4">
        <Card className="w-full max-w-sm">
          <CardContent className="pt-6 text-center">
            <p className="text-destructive font-medium">{error || "エラーが発生しました"}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (saved) {
    return (
      <div className="flex items-center justify-center min-h-screen p-4">
        <Card className="w-full max-w-sm">
          <CardContent className="pt-6 text-center space-y-4">
            <CheckCircle className="h-16 w-16 text-green-500 mx-auto" />
            <h2 className="text-xl font-bold">送信完了</h2>
            <p className="text-muted-foreground">
              {info.employee_name}さんの{parseInt(month.split("-")[1])}月のシフト希望を受け付けました。
            </p>
            <p className="text-sm text-muted-foreground">
              希望変更がありましたら、若生さんまでお伝えください。
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const [calYear, calMonth] = month.split("-").map(Number);

  // Show read-only summary if already submitted
  if (info.existing_request) {
    const req = info.existing_request;
    const periodLabel = (p: string) => p === "all_day" ? "終日" : p === "am" ? "午前" : "午後";
    return (
      <div className="min-h-screen bg-gray-50 p-3 sm:p-4 max-w-lg mx-auto">
        <div className="mb-4">
          <h1 className="text-lg font-bold">
            {info.employee_name}さん — {calMonth}月 シフト希望
          </h1>
          <Badge variant="outline" className="mt-1 border-green-500 text-green-700">
            入力済み
          </Badge>
        </div>

        <Card className="mb-4">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">送信済みの希望内容</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {req.details.length > 0 && (
              <div>
                <Label className="text-sm font-medium">希望休日</Label>
                <ul className="mt-1 space-y-1">
                  {req.details
                    .slice()
                    .sort((a, b) => a.date.localeCompare(b.date))
                    .map((d, i) => (
                      <li key={i} className="text-sm text-muted-foreground">
                        {d.date}（{periodLabel(d.period)}）
                      </li>
                    ))}
                </ul>
              </div>
            )}
            {req.requested_work_days && (
              <div>
                <Label className="text-sm font-medium">希望出勤日数</Label>
                <p className="text-sm text-muted-foreground mt-1">
                  {req.requested_work_days === "max" ? "なるべく多く" : `${req.requested_work_days}日以内`}
                </p>
              </div>
            )}
            {req.weekly_work_day_limit != null && (
              <div>
                <Label className="text-sm font-medium">週間出勤上限</Label>
                <p className="text-sm text-muted-foreground mt-1">週{req.weekly_work_day_limit}日以内</p>
              </div>
            )}
            {req.note && (
              <div>
                <Label className="text-sm font-medium">備考</Label>
                <p className="text-sm text-muted-foreground mt-1">{req.note}</p>
              </div>
            )}
          </CardContent>
        </Card>

        <p className="text-sm text-muted-foreground text-center">
          希望変更がありましたら、若生さんまでお伝えください。
        </p>
      </div>
    );
  }

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
    <div className="min-h-screen bg-gray-50 p-3 sm:p-4 max-w-lg mx-auto">
      <div className="mb-4">
        <h1 className="text-lg font-bold">
          {info.employee_name}さん — {calMonth}月 シフト希望入力
        </h1>
      </div>

      <Card className="mb-4">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">希望休日</CardTitle>
          <p className="text-xs text-muted-foreground">休みたい日の午前・午後をタップしてください</p>
        </CardHeader>
        <CardContent>
          <div className="select-none">
            <div className="grid grid-cols-7 gap-1 text-center text-xs font-medium text-muted-foreground mb-1">
              {["日", "月", "火", "水", "木", "金", "土"].map((d) => (
                <div key={d}>{d}</div>
              ))}
            </div>
            {calendarWeeks.map((week, wi) => (
              <div key={wi} className="grid grid-cols-7 gap-1 mb-1">
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
                      <div className={`text-center text-xs py-0.5 font-medium ${dow === 0 ? "text-red-400" : dow === 6 ? "text-blue-400" : ""}`}>
                        {day}
                      </div>
                      {isNonWorking ? (
                        <div className="h-[44px]" />
                      ) : (
                        <div className="flex flex-col">
                          <button
                            type="button"
                            onClick={() => togglePeriod(dateStr, "am")}
                            className={`h-[22px] text-[11px] leading-none transition-colors active:opacity-70 ${amSelected ? "bg-blue-500 text-white" : "hover:bg-blue-100"}`}
                          >
                            午前
                          </button>
                          <button
                            type="button"
                            onClick={() => togglePeriod(dateStr, "pm")}
                            className={`h-[22px] text-[11px] leading-none transition-colors active:opacity-70 ${pmSelected ? "bg-blue-500 text-white" : "hover:bg-blue-100"}`}
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
          <p className="mt-2 text-xs text-muted-foreground">
            選択中: {selectedDaysOff.size}件（午前/午後）
          </p>
        </CardContent>
      </Card>

      <Card className="mb-4">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">その他の設定</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <Label className="text-sm">希望出勤日数</Label>
            <Select value={workDays} onValueChange={setWorkDays}>
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="選択してください" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">未選択</SelectItem>
                <SelectItem value="max">なるべく多く</SelectItem>
                {Array.from({ length: 23 }, (_, i) => 23 - i).map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n}日以内
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-sm">週間出勤上限</Label>
            <Select value={weeklyLimit} onValueChange={setWeeklyLimit}>
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="設定なし" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">設定なし</SelectItem>
                <SelectItem value="4">週4日以内</SelectItem>
                <SelectItem value="3">週3日以内</SelectItem>
                <SelectItem value="2">週2日以内</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-sm">備考</Label>
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="mt-1"
              placeholder="自由記述"
              rows={3}
            />
          </div>
        </CardContent>
      </Card>

      <Button
        onClick={handleSubmit}
        disabled={saving}
        className="w-full h-14 text-lg font-bold"
        size="lg"
      >
        <Send className="mr-2 h-5 w-5" />
        {saving ? "送信中..." : "シフト希望を送信"}
      </Button>
    </div>
  );
}
