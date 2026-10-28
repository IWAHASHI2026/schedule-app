from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import (
    get_db, Schedule, ShiftAssignment, Employee, ShiftRequest,
    RequestDetail, JobType, employee_default_work_days,
)
from models import ReportOut, EmployeeReportOut
from routers.holidays import is_non_working_day, get_company_holiday_dates
from services.schedule_select import select_display_schedule, prev_month_week_assignments
from datetime import date
from collections import defaultdict
import calendar

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _available_days(
    working_dates: list[date],
    full_off: set[date],
    half_off: set[date],
    weekly_limit: int | None,
    carried_days: int,
    carry_week_key,
) -> float:
    """出勤できる最大日数。希望休・半日休（0.5日）・週上限・前月からの持ち越しを考慮する。
    生成側（optimizer の SC-01）と同じ数え方。「調整休」= この日数 − 実際の出勤日数。"""
    weeks: dict[tuple, list[date]] = defaultdict(list)
    for d in working_dates:
        weeks[d.isocalendar()[:2]].append(d)
    total = 0.0
    for week_key, days in weeks.items():
        units = sorted(
            (0.0 if d in full_off else (0.5 if d in half_off else 1.0) for d in days),
            reverse=True,
        )
        if weekly_limit is not None:
            limit = max(0, weekly_limit - (carried_days if week_key == carry_week_key else 0))
            units = units[:limit]
        total += sum(units)
    return total


def _generate_comment(
    total_work: float,
    total_off: int,
    requested_work_days: str | None,
    weekly_work_day_limit: int | None,
    num_requested_off_days: int,
    total_working_dates: int,
    is_default: bool = False,
    available_days: float | None = None,
) -> str:
    """スタッフごとの希望充足コメントを生成する。"""
    parts: list[str] = []

    # 希望出勤 vs 実績
    if requested_work_days == "max":
        if total_work >= total_working_dates:
            parts.append(f"全{total_working_dates}営業日出勤")
        else:
            gap = total_working_dates - total_work
            # 調整休 = 出勤できた最大日数 − 実際の出勤日数
            # （希望休だけでなく週上限・半日休・前月からの持ち越しも除いた日数）
            if available_days is not None:
                adjusted_gap = available_days - total_work
            else:
                adjusted_gap = gap - num_requested_off_days
            tw = int(total_work) if total_work == int(total_work) else total_work
            if adjusted_gap > 0:
                ag_s = int(adjusted_gap) if adjusted_gap == int(adjusted_gap) else adjusted_gap
                parts.append(f"{total_working_dates}営業日中{tw}日出勤（調整休{ag_s}日）")
            else:
                parts.append(f"{total_working_dates}営業日中{tw}日出勤")
    elif requested_work_days is not None:
        limit = int(requested_work_days)
        tw = int(total_work) if total_work == int(total_work) else total_work
        if total_work >= limit:
            parts.append(f"上限{limit}日に対し{tw}日出勤（達成）")
        else:
            diff = limit - total_work
            diff_s = int(diff) if diff == int(diff) else diff
            parts.append(f"上限{limit}日に対し{tw}日出勤（{diff_s}日余裕）")
    else:
        tw = int(total_work) if total_work == int(total_work) else total_work
        parts.append(f"{tw}日出勤（希望未設定）")
    if is_default:
        parts.append("希望未入力のため既定値で計算")

    # 週間上限
    if weekly_work_day_limit is not None:
        parts.append(f"週{weekly_work_day_limit}日制約あり")

    # 希望休
    if num_requested_off_days > 0:
        parts.append(f"希望休{num_requested_off_days}日反映済")

    return "。".join(parts)


@router.get("", response_model=ReportOut)
def get_report(month: str, db: Session = Depends(get_db)):
    # 公開中 > 確定 > 最新 の順で、その月のシフトを選ぶ（画面・出力と同じ基準）
    schedule = select_display_schedule(db, month)
    if not schedule:
        return ReportOut(month=month)

    job_types = db.query(JobType).order_by(JobType.sort_order).all()
    jt_map = {jt.id: jt.name for jt in job_types}

    assignments = (
        db.query(ShiftAssignment)
        .filter(ShiftAssignment.schedule_id == schedule.id)
        .all()
    )
    # 在籍者と、このシフトに載っている退職者を表示する
    present = {a.employee_id for a in assignments}
    employees = [
        e for e in db.query(Employee).order_by(Employee.sort_order).all()
        if e.retired_at is None or e.id in present
    ]

    # Count total working dates in the month
    year, mon = map(int, month.split("-"))
    days_in_month = calendar.monthrange(year, mon)[1]
    all_dates = [date(year, mon, d) for d in range(1, days_in_month + 1)]
    company_holidays = get_company_holiday_dates(db)
    total_working_dates = sum(1 for d in all_dates if not is_non_working_day(d, company_holidays))
    working_dates = [d for d in all_dates if not is_non_working_day(d, company_holidays)]
    # 月初の週が前月から続く場合の、前月の出勤日数（週上限の計算で差し引く）
    first_day = date(year, mon, 1)
    carried_jobs = prev_month_week_assignments(db, first_day)
    carried_days = {e_id: len(jobs) for e_id, jobs in carried_jobs.items()}
    carry_week_key = first_day.isocalendar()[:2]
    craft_names = {"職人", "サブ職人"}

    emp_reports = []

    for emp in employees:
        emp_assignments = [a for a in assignments if a.employee_id == emp.id]
        off_types = ("off", "requested_off", "adjusted_off")
        work_assignments = [a for a in emp_assignments if a.work_type not in off_types]
        off_assignments = [a for a in emp_assignments if a.work_type in off_types]

        total_work = sum(a.headcount_value for a in work_assignments)
        total_off = len([a for a in off_assignments if not is_non_working_day(a.date, company_holidays)])

        jt_counts: dict[str, float] = {}
        for a in work_assignments:
            jt_name = jt_map.get(a.job_type_id, "不明")
            jt_counts[jt_name] = jt_counts.get(jt_name, 0) + a.headcount_value

        # Get request data
        req = (
            db.query(ShiftRequest)
            .filter(ShiftRequest.employee_id == emp.id, ShiftRequest.target_month == month)
            .first()
        )
        rw = str(req.requested_work_days) if req and req.requested_work_days is not None else None
        wl = req.weekly_work_day_limit if req else None
        # 希望が未入力なら、生成と同じ既定値を使って表示する
        is_default = req is None
        if is_default:
            rw = employee_default_work_days(emp)

        # Count requested off days on working days only (distinct dates)
        # 祝日・土日の希望休は営業日数に影響しないためカウントしない
        num_off_days = 0
        full_off: set[date] = set()
        half_off: set[date] = set()
        if req:
            details = db.query(RequestDetail).filter(
                RequestDetail.shift_request_id == req.id
            ).all()
            num_off_days = len(set(d.date for d in details if not is_non_working_day(d.date, company_holidays)))
            periods: dict[date, set[str]] = defaultdict(set)
            for d in details:
                periods[d.date].update({"am", "pm"} if (d.period or "all_day") == "all_day" else {d.period})
            for d, p in periods.items():
                (full_off if len(p) == 2 else half_off).add(d)
        # 職人・サブ職人しかできない人の半日休は終日休として扱われる（生成側と同じ）
        if emp.job_types and {ejt.job_type.name for ejt in emp.job_types} <= craft_names:
            full_off |= half_off
            half_off = set()
        available = _available_days(
            working_dates, full_off, half_off, wl, carried_days.get(emp.id, 0), carry_week_key,
        )

        comment = _generate_comment(
            total_work, total_off, rw, wl,
            num_off_days, total_working_dates, is_default, available,
        )

        emp_reports.append(EmployeeReportOut(
            employee_id=emp.id,
            employee_name=emp.name,
            total_work_days=total_work,
            total_days_off=total_off,
            requested_work_days=rw,
            weekly_work_day_limit=wl,
            job_type_counts=jt_counts,
            comment=comment,
        ))

    return ReportOut(
        month=month,
        employees=emp_reports,
    )
