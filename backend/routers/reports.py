from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, Schedule, ShiftAssignment, Employee, ShiftRequest, JobType
from models import ReportOut, EmployeeReportOut
from routers.holidays import is_non_working_day

router = APIRouter(prefix="/api/reports", tags=["reports"])


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
    job_types = db.query(JobType).all()
    jt_map = {jt.id: jt.name for jt in job_types}

    assignments = (
        db.query(ShiftAssignment)
        .filter(ShiftAssignment.schedule_id == schedule.id)
        .all()
    )

    emp_reports = []
    work_days_list = []

    for emp in employees:
        emp_assignments = [a for a in assignments if a.employee_id == emp.id]
        work_assignments = [a for a in emp_assignments if a.work_type != "off"]
        off_assignments = [a for a in emp_assignments if a.work_type == "off"]

        total_work = sum(a.headcount_value for a in work_assignments)
        total_off = len([a for a in off_assignments if not is_non_working_day(a.date)])

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

        emp_reports.append(EmployeeReportOut(
            employee_id=emp.id,
            employee_name=emp.name,
            total_work_days=total_work,
            total_days_off=total_off,
            requested_work_days=str(req.requested_work_days) if req and req.requested_work_days is not None else None,
            job_type_counts=jt_counts,
        ))
        work_days_list.append(total_work)

    fairness_max = max(work_days_list) if work_days_list else 0
    fairness_min = min(work_days_list) if work_days_list else 0

    return ReportOut(
        month=month,
        employees=emp_reports,
        fairness_max=fairness_max,
        fairness_min=fairness_min,
        fairness_diff=fairness_max - fairness_min,
    )
