from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import (
    get_db, Schedule, ShiftAssignment, Employee, ShiftRequest,
    RequestDetail, JobType,
)
from models import ReportOut, EmployeeReportOut
from routers.holidays import is_non_working_day, get_company_holiday_dates
from datetime import date
import calendar

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _generate_comment(
    total_work: float,
    total_off: int,
    requested_work_days: str | None,
    weekly_work_day_limit: int | None,
    num_requested_off_days: int,
    total_working_dates: int,
) -> str:
    """スタッフごとの希望充足コメントを生成する。"""
    parts: list[str] = []

    # 希望出勤 vs 実績
    if requested_work_days == "max":
        if total_work >= total_working_dates:
            parts.append(f"全{total_working_dates}営業日出勤")
        else:
            gap = total_working_dates - total_work
            # 希望休（営業日分）を差し引いた真の調整休を計算
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

    # 週間上限
    if weekly_work_day_limit is not None:
        parts.append(f"週{weekly_work_day_limit}日制約あり")

    # 希望休
    if num_requested_off_days > 0:
        parts.append(f"希望休{num_requested_off_days}日反映済")

    return "。".join(parts)


@router.get("", response_model=ReportOut)
def get_report(month: str, db: Session = Depends(get_db)):
    # Find latest schedule for the month
    schedule = (
        db.query(Schedule)
        .filter(Schedule.target_month == month)
        .order_by(Schedule.id.desc())
        .first()
    )
    if not schedule:
        return ReportOut(month=month)

    employees = db.query(Employee).order_by(Employee.sort_order).all()
    job_types = db.query(JobType).order_by(JobType.sort_order).all()
    jt_map = {jt.id: jt.name for jt in job_types}

    assignments = (
        db.query(ShiftAssignment)
        .filter(ShiftAssignment.schedule_id == schedule.id)
        .all()
    )

    # Count total working dates in the month
    year, mon = map(int, month.split("-"))
    days_in_month = calendar.monthrange(year, mon)[1]
    all_dates = [date(year, mon, d) for d in range(1, days_in_month + 1)]
    company_holidays = get_company_holiday_dates(db)
    total_working_dates = sum(1 for d in all_dates if not is_non_working_day(d, company_holidays))

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

        # Count requested off days on working days only (distinct dates)
        # 祝日・土日の希望休は営業日数に影響しないためカウントしない
        num_off_days = 0
        if req:
            details = db.query(RequestDetail).filter(
                RequestDetail.shift_request_id == req.id
            ).all()
            num_off_days = len(set(d.date for d in details if not is_non_working_day(d.date, company_holidays)))

        comment = _generate_comment(
            total_work, total_off, rw, wl,
            num_off_days, total_working_dates,
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
