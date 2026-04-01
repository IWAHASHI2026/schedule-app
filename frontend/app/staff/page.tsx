"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Pencil, Trash2, ArrowUp, ArrowDown, Link2, QrCode, Copy, LinkIcon, Unlink } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import {
  getEmployees, createEmployee, updateEmployee, deleteEmployee,
  updateEmployeeFull, reorderEmployees, getJobTypes,
  getEmployeeTokens, generateToken, revokeToken,
  type Employee, type JobType, type EmployeeToken,
} from "@/lib/api";

export default function StaffPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [jobTypes, setJobTypes] = useState<JobType[]>([]);
  const [newName, setNewName] = useState("");
  const [newEmploymentType, setNewEmploymentType] = useState("full_time");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editJobTypes, setEditJobTypes] = useState<number[]>([]);
  const [editEmploymentType, setEditEmploymentType] = useState("full_time");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [tokens, setTokens] = useState<EmployeeToken[]>([]);
  const [qrDialogOpen, setQrDialogOpen] = useState(false);
  const [qrToken, setQrToken] = useState<EmployeeToken | null>(null);
  const [printMode, setPrintMode] = useState(false);

  // 対象月（デフォルト翌月）
  const today = new Date();
  const nextMonth = new Date(today.getFullYear(), today.getMonth() + 1, 1);
  const defaultLinkMonth = `${nextMonth.getFullYear()}-${String(nextMonth.getMonth() + 1).padStart(2, "0")}`;
  const [linkMonth, setLinkMonth] = useState(defaultLinkMonth);
  const [linkYear, linkMon] = linkMonth.split("-").map(Number);

  const load = async () => {
    const [emps, jts, tks] = await Promise.all([getEmployees(), getJobTypes(), getEmployeeTokens()]);
    setEmployees(emps);
    setJobTypes(jts);
    setTokens(tks);
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    await createEmployee(newName.trim(), newEmploymentType);
    setNewName("");
    setNewEmploymentType("full_time");
    load();
  };

  const handleDelete = async (id: number) => {
    if (!confirm("このスタッフを削除しますか？")) return;
    await deleteEmployee(id);
    load();
  };

  const openEdit = (emp: Employee) => {
    setEditingId(emp.id);
    setEditName(emp.name);
    setEditEmploymentType(emp.employment_type || "full_time");
    setEditJobTypes(emp.job_types.map((jt) => jt.id));
    setDialogOpen(true);
  };

  const handleSaveEdit = async () => {
    if (editingId === null) return;
    try {
      await updateEmployeeFull(editingId, editName, editEmploymentType, editJobTypes);
      setDialogOpen(false);
      setEditingId(null);
      await load();
    } catch (e) {
      alert("保存に失敗しました。もう一度お試しください。");
    }
  };

  const toggleJobType = (jtId: number) => {
    setEditJobTypes((prev) =>
      prev.includes(jtId) ? prev.filter((id) => id !== jtId) : [...prev, jtId]
    );
  };

  const getStaffUrl = (staffToken: string) => {
    const base = typeof window !== "undefined" ? window.location.origin : "";
    return `${base}/staff-request/${staffToken}?month=${linkMonth}`;
  };

  const handleGenerateToken = async (empId: number) => {
    await generateToken(empId);
    load();
  };

  const handleRevokeToken = async (empId: number) => {
    if (!confirm("このリンクを無効化しますか？")) return;
    await revokeToken(empId);
    load();
  };

  const handleGenerateAll = async () => {
    const missing = tokens.filter((t) => !t.staff_token);
    if (missing.length === 0) { alert("全員のリンクが生成済みです"); return; }
    for (const t of missing) {
      await generateToken(t.employee_id);
    }
    load();
  };

  const handleCopyUrl = async (staffToken: string) => {
    await navigator.clipboard.writeText(getStaffUrl(staffToken));
    alert("URLをコピーしました");
  };

  const handleShowQr = (t: EmployeeToken) => {
    setQrToken(t);
    setQrDialogOpen(true);
  };

  const handleMove = async (index: number, direction: "up" | "down") => {
    const newIndex = direction === "up" ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= employees.length) return;
    const reordered = [...employees];
    [reordered[index], reordered[newIndex]] = [reordered[newIndex], reordered[index]];
    setEmployees(reordered);
    try {
      await reorderEmployees(reordered.map((e) => e.id));
    } catch {
      await load();
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">スタッフ管理</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">新規スタッフ登録</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 items-end">
            <Input
              placeholder="氏名を入力"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              className="max-w-xs"
            />
            <Select value={newEmploymentType} onValueChange={setNewEmploymentType}>
              <SelectTrigger className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="full_time">フル勤務</SelectItem>
                <SelectItem value="dependent">扶養内</SelectItem>
              </SelectContent>
            </Select>
            <Button onClick={handleCreate}>
              <Plus className="mr-2 h-4 w-4" />
              登録
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">スタッフ一覧（{employees.length}名）</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-2 px-3 text-center w-16">順番</th>
                  <th className="py-2 px-3 text-left">氏名</th>
                  <th className="py-2 px-3 text-left">属性</th>
                  <th className="py-2 px-3 text-left">担当可能な仕事種類</th>
                  <th className="py-2 px-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {employees.map((emp, idx) => (
                  <tr key={emp.id} className="border-b hover:bg-muted/50">
                    <td className="py-2 px-3">
                      <div className="flex items-center justify-center gap-0.5">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0"
                          disabled={idx === 0}
                          onClick={() => handleMove(idx, "up")}
                        >
                          <ArrowUp className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0"
                          disabled={idx === employees.length - 1}
                          onClick={() => handleMove(idx, "down")}
                        >
                          <ArrowDown className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                    <td className="py-2 px-3 font-medium">{emp.name}</td>
                    <td className="py-2 px-3">
                      <Badge
                        variant="outline"
                        className={emp.employment_type === "dependent" ? "border-green-500 text-green-700" : "border-blue-500 text-blue-700"}
                      >
                        {emp.employment_type === "dependent" ? "扶養内" : "フル勤務"}
                      </Badge>
                    </td>
                    <td className="py-2 px-3">
                      <div className="flex flex-wrap gap-1">
                        {emp.job_types.length > 0 ? (
                          emp.job_types.map((jt) => (
                            <Badge
                              key={jt.id}
                              style={{ backgroundColor: jt.color || undefined }}
                              className="text-white text-xs"
                            >
                              {jt.name}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-muted-foreground">未設定</span>
                        )}
                      </div>
                    </td>
                    <td className="py-2 px-3 text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => openEdit(emp)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDelete(emp.id)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
                {employees.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-muted-foreground">
                      スタッフが登録されていません
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center justify-between flex-wrap gap-2">
            <span>{linkYear}年{linkMon}月シフト — 希望入力リンク管理</span>
            <div className="flex gap-2 items-center">
              <Input
                type="month"
                value={linkMonth}
                onChange={(e) => setLinkMonth(e.target.value)}
                className="w-40 h-8 text-sm"
              />
              <Button variant="outline" size="sm" onClick={() => setPrintMode(true)}>
                <QrCode className="mr-1 h-4 w-4" />
                全員分QR印刷
              </Button>
              <Button size="sm" onClick={handleGenerateAll}>
                <Link2 className="mr-1 h-4 w-4" />
                全員一括生成
              </Button>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-2 px-3 text-left">氏名</th>
                  <th className="py-2 px-3 text-left">リンク状態</th>
                  <th className="py-2 px-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {tokens.map((t) => (
                  <tr key={t.employee_id} className="border-b hover:bg-muted/50">
                    <td className="py-2 px-3 font-medium">{t.employee_name}</td>
                    <td className="py-2 px-3">
                      {t.staff_token ? (
                        <Badge variant="outline" className="border-green-500 text-green-700">有効</Badge>
                      ) : (
                        <Badge variant="secondary">未生成</Badge>
                      )}
                    </td>
                    <td className="py-2 px-3 text-right">
                      <div className="flex justify-end gap-1">
                        {t.staff_token ? (
                          <>
                            <Button variant="ghost" size="sm" onClick={() => handleShowQr(t)} title="QR表示">
                              <QrCode className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => handleCopyUrl(t.staff_token!)} title="URLコピー">
                              <Copy className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => handleRevokeToken(t.employee_id)} title="リンク無効化">
                              <Unlink className="h-4 w-4 text-destructive" />
                            </Button>
                          </>
                        ) : (
                          <Button variant="outline" size="sm" onClick={() => handleGenerateToken(t.employee_id)}>
                            <LinkIcon className="mr-1 h-4 w-4" />
                            リンク生成
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={qrDialogOpen} onOpenChange={setQrDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{qrToken?.employee_name} — {linkYear}年{linkMon}月シフト QRコード</DialogTitle>
          </DialogHeader>
          {qrToken?.staff_token && (
            <div className="flex flex-col items-center gap-4 py-4">
              <QRCodeSVG value={getStaffUrl(qrToken.staff_token)} size={200} />
              <p className="text-xs text-muted-foreground text-center break-all max-w-[280px]">
                {getStaffUrl(qrToken.staff_token)}
              </p>
              <Button variant="outline" onClick={() => handleCopyUrl(qrToken.staff_token!)}>
                <Copy className="mr-2 h-4 w-4" />
                URLをコピー
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {printMode && (
        <Dialog open={printMode} onOpenChange={setPrintMode}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto print:max-h-none print:overflow-visible">
            <DialogHeader>
              <DialogTitle>{linkYear}年{linkMon}月シフト — 全員QRコード（印刷用）</DialogTitle>
            </DialogHeader>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-6 py-4 print:grid-cols-3">
              {tokens.filter((t) => t.staff_token).map((t) => (
                <div key={t.employee_id} className="flex flex-col items-center gap-2 border p-3 rounded">
                  <p className="font-bold text-sm">{t.employee_name}</p>
                  <p className="text-xs text-muted-foreground">{linkYear}年{linkMon}月シフト希望</p>
                  <QRCodeSVG value={getStaffUrl(t.staff_token!)} size={120} />
                </div>
              ))}
            </div>
            <Button onClick={() => window.print()} className="w-full print:hidden">
              印刷
            </Button>
          </DialogContent>
        </Dialog>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>スタッフ編集</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>氏名</Label>
              <Input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <Label>属性</Label>
              <Select value={editEmploymentType} onValueChange={setEditEmploymentType}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="full_time">フル勤務</SelectItem>
                  <SelectItem value="dependent">扶養内</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>担当可能な仕事種類</Label>
              <div className="mt-2 space-y-2">
                {jobTypes.map((jt) => (
                  <div key={jt.id} className="flex items-center space-x-2">
                    <Checkbox
                      id={`jt-${jt.id}`}
                      checked={editJobTypes.includes(jt.id)}
                      onCheckedChange={() => toggleJobType(jt.id)}
                    />
                    <Label htmlFor={`jt-${jt.id}`} className="flex items-center gap-2">
                      <span
                        className="inline-block h-3 w-3 rounded-full"
                        style={{ backgroundColor: jt.color || "#ccc" }}
                      />
                      {jt.name}
                    </Label>
                  </div>
                ))}
              </div>
            </div>
            <Button onClick={handleSaveEdit} className="w-full">
              保存
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
