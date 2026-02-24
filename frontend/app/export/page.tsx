"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { FileSpreadsheet, FileText, Download } from "lucide-react";
import { getExportUrl } from "@/lib/api";

export default function ExportPage() {
  const today = new Date();
  const defaultMonth = `${today.getFullYear()}-${String(today.getMonth() + 2).padStart(2, "0")}`;
  const [month, setMonth] = useState(defaultMonth);

  const handleDownload = (type: "csv" | "excel" | "pdf") => {
    window.open(getExportUrl(type, month), "_blank");
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">シフト出力</h1>

      <div>
        <Label>対象月</Label>
        <Input
          type="month"
          value={month}
          onChange={(e) => setMonth(e.target.value)}
          className="mt-1 w-44"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5" />
              CSV出力
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">
              カンマ区切りのCSVファイルとしてダウンロードします。Excel等で開けます。
            </p>
            <Button onClick={() => handleDownload("csv")} className="w-full">
              <Download className="mr-2 h-4 w-4" />
              CSVダウンロード
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5 text-green-600" />
              Excel出力
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">
              色分けされたExcelファイル(.xlsx)としてダウンロードします。
            </p>
            <Button onClick={() => handleDownload("excel")} className="w-full">
              <Download className="mr-2 h-4 w-4" />
              Excelダウンロード
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <FileText className="h-5 w-5 text-red-600" />
              PDF出力
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">
              印刷用A3横レイアウトのPDFとしてダウンロードします。
            </p>
            <Button onClick={() => handleDownload("pdf")} className="w-full">
              <Download className="mr-2 h-4 w-4" />
              PDFダウンロード
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
