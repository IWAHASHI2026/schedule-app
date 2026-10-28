"""月のシフトのうち、どれを「その月のシフト」として扱うかを一か所で決める。

優先順位: 公開中 > 確定 > 最新（生成が新しいもの）。
集計・出力・月またぎの週の計算と、画面側（frontend/lib/api.ts の pickDisplaySchedule）で
同じ選び方をする。画面ごとに違う版を見せないため。
"""
from sqlalchemy.orm import Session
from database import Schedule

STATUS_PRIORITY = ("published", "confirmed")


def pick_display_schedule(schedules: list[Schedule]) -> Schedule | None:
    """新しい順に並んだリストから表示対象を選ぶ。"""
    for status in STATUS_PRIORITY:
        for s in schedules:
            if s.status == status:
                return s
    return schedules[0] if schedules else None


def select_display_schedule(db: Session, month: str) -> Schedule | None:
    schedules = (
        db.query(Schedule)
        .filter(Schedule.target_month == month)
        .order_by(Schedule.id.desc())
        .all()
    )
    return pick_display_schedule(schedules)
