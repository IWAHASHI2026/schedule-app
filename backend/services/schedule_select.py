"""月のシフトのうち、どれを「その月のシフト」として扱うかを一か所で決める。

優先順位: 公開中 > 確定 > 最新（生成が新しいもの）。
集計・出力・月またぎの週の計算と、画面側（frontend/lib/api.ts の pickDisplaySchedule）で
同じ選び方をする。画面ごとに違う版を見せないため。
"""
from datetime import date, timedelta
from sqlalchemy.orm import Session
from database import Schedule, ShiftAssignment

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


def prev_month_week_assignments(db: Session, month_start: date) -> dict[int, dict[date, int]]:
    """月初の週が前月から続いている場合に、前月のシフトでその週に出勤した日と職種を返す。

    Returns: e_id -> {date: job_type_id}。半日勤務も1日として数える（週の出勤上限と同じ数え方）。
    週の出勤上限（HC-07）、手紙の週上限（SC-12）、集計の「調整休」で使う。
    月初が月曜の場合と、前月のシフトが無い場合は空。
    """
    week_start = month_start - timedelta(days=month_start.weekday())  # その週の月曜
    if week_start == month_start:
        return {}

    prev_month = f"{week_start.year:04d}-{week_start.month:02d}"
    # 同じ月に複数のシフトがあるので、画面・出力と同じ基準（公開中 > 確定 > 最新）で選ぶ
    prev_schedule = select_display_schedule(db, prev_month)
    if prev_schedule is None:
        return {}

    prev_assignments = (
        db.query(ShiftAssignment)
        .filter(
            ShiftAssignment.schedule_id == prev_schedule.id,
            ShiftAssignment.date >= week_start,
            ShiftAssignment.date < month_start,
        )
        .all()
    )
    worked: dict[int, dict[date, int]] = {}
    for a in prev_assignments:
        if a.job_type_id is None or a.work_type in ("off", "requested_off", "adjusted_off"):
            continue
        worked.setdefault(a.employee_id, {})[a.date] = a.job_type_id
    return worked
