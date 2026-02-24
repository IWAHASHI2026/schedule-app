"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Plus, Pencil, Trash2 } from "lucide-react";
import {
  getEmployees, createEmployee, updateEmployee, deleteEmployee,
  updateEmployeeJobTypes, getJobTypes,
  type Employee, type JobType,
} from "@/lib/api";

export default function StaffPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [jobTypes, setJobTypes] = useState<JobType[]>([]);
  const [newName, setNewName] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editJobTypes, setEditJobTypes] = useState<number[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);

  const load = async () => {
    const [emps, jts] = await Promise.all([getEmployees(), getJobTypes()]);
    setEmployees(emps);
    setJobTypes(jts);
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    await createEmployee(newName.trim());
    setNewName("");
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
    setEditJobTypes(emp.job_types.map((jt) => jt.id));
    setDialogOpen(true);
  };

  const handleSaveEdit = async () => {
    if (editingId === null) return;
    await updateEmployee(editingId, editName);
    await updateEmployeeJobTypes(editingId, editJobTypes);
    setDialogOpen(false);
    setEditingId(null);
    load();
  };

  const toggleJobType = (jtId: number) => {
    setEditJobTypes((prev) =>
      prev.includes(jtId) ? prev.filter((id) => id !== jtId) : [...prev, jtId]
    );
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">スタッフ管理</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">新規スタッフ登録</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="氏名を入力"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              className="max-w-xs"
            />
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
                  <th className="py-2 px-3 text-left">ID</th>
                  <th className="py-2 px-3 text-left">氏名</th>
                  <th className="py-2 px-3 text-left">担当可能な仕事種類</th>
                  <th className="py-2 px-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {employees.map((emp) => (
                  <tr key={emp.id} className="border-b hover:bg-muted/50">
                    <td className="py-2 px-3">{emp.id}</td>
                    <td className="py-2 px-3 font-medium">{emp.name}</td>
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
                    <td colSpan={4} className="py-8 text-center text-muted-foreground">
                      スタッフが登録されていません
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

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
