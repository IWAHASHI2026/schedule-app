"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ShiftRequest, Employee } from "@/lib/api";

// 対象月の全スタッフの備考を一覧表示する読み取り専用カード
export default function NotesSummary({
  requests,
  employees,
}: {
  requests: ShiftRequest[];
  employees: Employee[];
}) {
  const order = new Map(employees.map((e, i) => [e.id, i]));
  const notes = requests
    .filter((r) => r.note && r.note.trim() !== "")
    .sort((a, b) => (order.get(a.employee_id) ?? 999) - (order.get(b.employee_id) ?? 999));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">備考一覧</CardTitle>
      </CardHeader>
      <CardContent>
        {notes.length === 0 ? (
          <p className="text-sm text-muted-foreground">備考はありません</p>
        ) : (
          <div className="space-y-2">
            {notes.map((r) => (
              <div key={r.employee_id} className="flex gap-3 text-sm border-b pb-2 last:border-b-0 last:pb-0">
                <span className="font-medium shrink-0 w-24">{r.employee_name}</span>
                <span className="whitespace-pre-wrap text-muted-foreground">{r.note}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
