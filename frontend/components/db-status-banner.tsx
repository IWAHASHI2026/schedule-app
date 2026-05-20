"use client";

import { useEffect, useState, useRef } from "react";
import { getHealth } from "@/lib/api";

export default function DbStatusBanner() {
  const [show, setShow] = useState(false);
  const failsRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const h = await getHealth();
        if (cancelled) return;
        if (h.db_connected) {
          failsRef.current = 0;
          setShow(false);
        } else {
          failsRef.current += 1;
          if (failsRef.current >= 2) setShow(true);
        }
      } catch {
        // backend 自体に到達不可 (デプロイ中/障害) も失敗として扱う
        if (cancelled) return;
        failsRef.current += 1;
        if (failsRef.current >= 2) setShow(true);
      }
    };
    check();
    const id = setInterval(check, 20000); // 20秒ごとに再確認
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (!show) return null;

  return (
    <div className="fixed top-0 inset-x-0 z-50 bg-red-600 text-white text-center text-xs sm:text-sm py-2 px-4 shadow-md">
      ⚠️ データベースに接続できません。<strong>データは消えていません</strong>。サーバーの復旧をお待ちください（自動で再確認しています）。
    </div>
  );
}
