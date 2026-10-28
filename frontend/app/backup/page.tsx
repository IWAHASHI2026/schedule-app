"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Download, Upload, AlertTriangle, CheckCircle } from "lucide-react";

const API_BASE = "/api";

export default function BackupPage() {
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleBackup = async () => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE}/backup`);
      if (!res.ok) throw new Error("バックアップの取得に失敗しました");
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const now = new Date();
      const ts = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}_${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(2, "0")}`;
      a.download = `shift_backup_${ts}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setStatus({ type: "success", message: "バックアップをダウンロードしました" });
    } catch (e: unknown) {
      setStatus({ type: "error", message: e instanceof Error ? e.message : "エラーが発生しました" });
    } finally {
      setLoading(false);
    }
  };

  const handleRestore = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;

    if (!confirm("バックアップの内容で現在のデータを置き換えます（スタッフ・希望・必要人数・休業日・カス取り・生成済みシフト）。よろしいですか？")) return;

    setLoading(true);
    setStatus(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/backup/restore`, {
        method: "POST",
        body: formData,
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || "復元に失敗しました");
      const schedulesPart =
        result.restored?.schedules == null
          ? "シフト: 旧形式のため変更なし"
          : `シフト: ${result.restored.schedules}件`;
      setStatus({
        type: "success",
        message: `データを復元しました（スタッフ: ${result.restored?.employees || 0}名、希望: ${result.restored?.shift_requests || 0}件、必要人数: ${result.restored?.daily_requirements || 0}件、${schedulesPart}）`,
      });
      if (fileRef.current) fileRef.current.value = "";
    } catch (e: unknown) {
      setStatus({ type: "error", message: e instanceof Error ? e.message : "エラーが発生しました" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">データ管理</h1>

      <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
        <div className="flex items-start gap-2">
          <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
          <div>
            <p className="font-medium text-yellow-800">定期的にバックアップを取得してください</p>
            <p className="text-sm text-yellow-700 mt-1">
              本番のデータベース（PostgreSQL）は更新しても消えませんが、万一の障害や別のサーバーへの移行に備えて、
              月に一度はバックアップをダウンロードしておくことをおすすめします。
            </p>
          </div>
        </div>
      </div>

      {status && (
        <div className={`rounded-lg border p-4 ${status.type === "success" ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"}`}>
          <div className="flex items-center gap-2">
            {status.type === "success" ? (
              <CheckCircle className="h-5 w-5 text-green-600" />
            ) : (
              <AlertTriangle className="h-5 w-5 text-red-600" />
            )}
            <p className={status.type === "success" ? "text-green-800" : "text-red-800"}>
              {status.message}
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Download className="h-5 w-5" />
              バックアップ
            </CardTitle>
            <CardDescription>
              スタッフ、希望入力、必要人数、休業日、カス取りスタッフ、生成済みシフト（状態・コメント・割当）の
              全データをJSONファイルとしてダウンロードします。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={handleBackup} disabled={loading} className="w-full">
              <Download className="mr-2 h-4 w-4" />
              バックアップをダウンロード
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-5 w-5" />
              データ復元
            </CardTitle>
            <CardDescription>
              バックアップファイルの内容で現在のデータを置き換えます。
              古い形式（シフトを含まない）のバックアップでは、今あるシフトはそのまま残ります。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <input
              ref={fileRef}
              type="file"
              accept=".json"
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-primary/10 file:text-primary hover:file:bg-primary/20"
            />
            <Button onClick={handleRestore} disabled={loading} variant="outline" className="w-full">
              <Upload className="mr-2 h-4 w-4" />
              復元する
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
