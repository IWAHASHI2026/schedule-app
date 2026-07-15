"use client";

import { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Trash2 } from "lucide-react";
import {
  getHolidays, addCompanyHoliday, deleteCompanyHoliday, getSchedules,
  type Holiday,
} from "@/lib/api";

export default function HolidaysPage() {
  const today = new Date();
  // 翌月をデフォルトに（年またぎはDateのロールオーバーで処理）
  const nextMonth = new Date(today.getFullYear(), today.getMonth() + 1, 1);
  const defaultMonth = `${nextMonth.getFullYear()}-${String(nextMonth.getMonth() + 1).padStart(2, "0")}`;
  const [month, setMonth] = useState(defaultMonth);
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [name, setName] = useState("臨時休業");
  const [hasSchedule, setHasSchedule] = useState(false);
  const [busy, setBusy] = useState(false);

  const year = parseInt(month.split("-")[0]);
  const loadSeq = useRef(0);

  const load = async () => {
    const seq = ++loadSeq.current;
    try {
      const [hols, schedules] = await Promise.all([
        getHolidays(year),
        getSchedules(month),
      ]);
      if (seq !== loadSeq.current) return; // 古いレスポンスは捨てる（月を素早く切り替えた場合）
      setHolidays(hols);
      setHasSchedule(schedules.length > 0);
    } catch {
      // 読み込み失敗時は前回の表示を維持
    }
  };

  useEffect(() => { load(); }, [month]);

  const holidayByDate = new Map(holidays.map((h) => [h.date, h]));
  const customHolidays = holidays.filter((h) => h.is_custom);

  const handleAdd = async (dateStr: string) => {
    if (busy) return;
    setBusy(true);
    try {
      await addCompanyHoliday(dateStr, name.trim() || "臨時休業");
      await load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "登録に失敗しました");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (h: Holiday) => {
    if (busy) return;
    const [, m, d] = h.date.split("-");
    if (!confirm(`${parseInt(m)}月${parseInt(d)}日「${h.name}」を削除しますか？`)) return;
    setBusy(true);
    try {
      await deleteCompanyHoliday(h.date);
      await load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "削除に失敗しました");
    } finally {
      setBusy(false);
    }
  };

  // Calendar generation（requests ページと同じパターン）
  const [calYear, calMonth] = month.split("-").map(Number);
  const daysInMonth = new Date(calYear, calMonth, 0).getDate();
  const firstDow = new Date(calYear, calMonth - 1, 1).getDay();

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
      <h1 className="text-2xl font-bold">休日設定</h1>
      <p className="text-sm text-muted-foreground">
        会社の臨時休業日（年末年始・お盆など）を登録します。
        登録した日は祝日と同様に、シフト自動生成・希望休入力・必要人数設定の対象外になります。
      </p>

      <Card className="border-yellow-500">
        <CardContent className="pt-4 text-sm space-y-1">
          <p>※ シフト生成後に休業日を追加・削除しても、生成済みのシフトには反映されません。休業日を変更した場合は対象月のシフトを再生成してください。</p>
          {hasSchedule && (
            <p className="font-medium text-yellow-700">
              ⚠ {calMonth}月のシフトは生成済みです。休業日を変更した場合は再生成が必要です。
            </p>
          )}
        </CardContent>
      </Card>

      <div className="flex gap-4 items-end">
        <div>
          <Label>対象月</Label>
          <Input
            type="month"
            value={month}
            onChange={(e) => { if (e.target.value) setMonth(e.target.value); }}
            className="mt-1 w-44"
          />
        </div>
        <div>
          <Label>休業名（追加時に使用）</Label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="例: 年末年始"
            className="mt-1 w-48"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">カレンダー（クリックで追加・削除）</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="select-none">
              <div className="grid grid-cols-7 gap-1 text-center text-sm font-medium mb-2">
                {["日", "月", "火", "水", "木", "金", "土"].map((d, i) => (
                  <div key={d} className={i === 0 ? "text-red-500" : i === 6 ? "text-blue-500" : "text-muted-foreground"}>
                    {d}
                  </div>
                ))}
              </div>
              {calendarWeeks.map((week, wi) => (
                <div key={wi} className="grid grid-cols-7 gap-1 mb-1">
                  {week.map((day, di) => {
                    if (day === null) return <div key={di} />;
                    const dateStr = `${calYear}-${String(calMonth).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                    const dow = new Date(calYear, calMonth - 1, day).getDay();
                    const isWeekend = dow === 0 || dow === 6;
                    const holiday = holidayByDate.get(dateStr);
                    const isNationalHoliday = !!holiday && !holiday.is_custom;
                    const isCompanyHoliday = !!holiday && !!holiday.is_custom;

                    if (isWeekend || isNationalHoliday) {
                      return (
                        <div key={di} className="rounded border bg-gray-100 text-gray-400 min-h-[52px] p-1">
                          <div className="text-center text-xs font-medium">{day}</div>
                          {isNationalHoliday && (
                            <div className="text-[10px] text-red-400 text-center leading-tight break-words">
                              {holiday.name}
                            </div>
                          )}
                        </div>
                      );
                    }

                    if (isCompanyHoliday) {
                      return (
                        <button
                          key={di}
                          onClick={() => handleDelete(holiday)}
                          disabled={busy}
                          className="rounded border border-orange-400 bg-orange-100 min-h-[52px] p-1 transition-colors hover:bg-orange-200"
                          title="クリックで削除"
                        >
                          <div className="text-center text-xs font-medium text-orange-700">{day}</div>
                          <div className="text-[10px] text-orange-700 text-center leading-tight break-words">
                            {holiday.name}
                          </div>
                        </button>
                      );
                    }

                    return (
                      <button
                        key={di}
                        onClick={() => handleAdd(dateStr)}
                        disabled={busy}
                        className="rounded border border-gray-200 min-h-[52px] p-1 transition-colors hover:bg-orange-50"
                        title="クリックで休業日として登録"
                      >
                        <div className="text-center text-xs font-medium">{day}</div>
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <span className="inline-block h-3 w-3 rounded bg-orange-100 border border-orange-400" />
                会社休業日（クリックで削除）
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-3 w-3 rounded bg-gray-100 border" />
                土日・祝日
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">登録済みの休業日（{year}年）</CardTitle>
          </CardHeader>
          <CardContent>
            {customHolidays.length === 0 ? (
              <p className="text-sm text-muted-foreground">登録された休業日はありません</p>
            ) : (
              <div className="space-y-1">
                {customHolidays.map((h) => {
                  const [, m, d] = h.date.split("-");
                  return (
                    <div key={h.date} className="flex items-center justify-between text-sm border-b py-1.5 last:border-b-0">
                      <span className="w-24 shrink-0 font-medium">{parseInt(m)}月{parseInt(d)}日</span>
                      <span className="flex-1 text-muted-foreground">{h.name}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-destructive hover:text-destructive"
                        onClick={() => handleDelete(h)}
                        disabled={busy}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
