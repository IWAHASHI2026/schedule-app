"""Full database backup and restore API.

Allows administrators to export all data as JSON and restore it,
preventing data loss on ephemeral platforms like Railway with SQLite.
"""

from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import (
    get_db, Employee, EmployeeJobType, JobType,
    ShiftRequest, RequestDetail, DailyRequirement,
    Schedule, ShiftAssignment, CompanyHoliday,
    KasutoriStaff, KasutoriAttendance,
)
from datetime import date, datetime
import json

router = APIRouter(prefix="/api/backup", tags=["backup"])


def _serialize_date(obj):
    """JSON serializer for date/datetime objects."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


@router.get("")
def export_backup(db: Session = Depends(get_db)):
    """Export all database data as JSON."""
    data = {
        "exported_at": datetime.utcnow().isoformat(),
        "job_types": [
            {"id": jt.id, "name": jt.name, "color": jt.color, "sort_order": jt.sort_order}
            for jt in db.query(JobType).order_by(JobType.sort_order).all()
        ],
        "employees": [
            {
                "id": e.id,
                "name": e.name,
                "employment_type": e.employment_type,
                "sort_order": e.sort_order,
                "staff_token": e.staff_token,
            }
            for e in db.query(Employee).order_by(Employee.sort_order).all()
        ],
        "employee_job_types": [
            {"employee_id": ejt.employee_id, "job_type_id": ejt.job_type_id}
            for ejt in db.query(EmployeeJobType).all()
        ],
        "shift_requests": [
            {
                "id": sr.id,
                "employee_id": sr.employee_id,
                "target_month": sr.target_month,
                "requested_work_days": sr.requested_work_days,
                "weekly_work_day_limit": sr.weekly_work_day_limit,
                "note": sr.note,
            }
            for sr in db.query(ShiftRequest).all()
        ],
        "request_details": [
            {
                "shift_request_id": rd.shift_request_id,
                "date": rd.date.isoformat(),
                "period": rd.period,
            }
            for rd in db.query(RequestDetail).all()
        ],
        "daily_requirements": [
            {
                "date": dr.date.isoformat(),
                "job_type_id": dr.job_type_id,
                "required_count": dr.required_count,
            }
            for dr in db.query(DailyRequirement).all()
        ],
        "company_holidays": [
            {"date": ch.date.isoformat(), "name": ch.name}
            for ch in db.query(CompanyHoliday).order_by(CompanyHoliday.date).all()
        ],
        "kasutori_staff": [
            {"id": s.id, "name": s.name, "sort_order": s.sort_order,
             "default_weekdays": s.default_weekdays}
            for s in db.query(KasutoriStaff).order_by(KasutoriStaff.sort_order).all()
        ],
        "kasutori_attendance": [
            {"staff_id": a.staff_id, "date": a.date.isoformat(), "is_working": a.is_working}
            for a in db.query(KasutoriAttendance).all()
        ],
    }
    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": "attachment; filename=shift_backup.json"
        },
    )


@router.post("/restore")
async def restore_backup(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Restore all data from a JSON backup file."""
    try:
        content = await file.read()
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return JSONResponse(status_code=400, content={"detail": f"Invalid JSON: {e}"})

    try:
        # Clear existing data in dependency order
        db.query(RequestDetail).delete()
        db.query(ShiftRequest).delete()
        db.query(ShiftAssignment).delete()
        db.query(Schedule).delete()
        db.query(DailyRequirement).delete()
        db.query(EmployeeJobType).delete()
        db.query(Employee).delete()
        db.query(JobType).delete()
        db.flush()

        # Restore job_types
        for jt in data.get("job_types", []):
            db.execute(
                JobType.__table__.insert().values(
                    id=jt["id"], name=jt["name"],
                    color=jt.get("color"), sort_order=jt.get("sort_order", 0),
                )
            )
        db.flush()

        # Restore employees
        for e in data.get("employees", []):
            db.execute(
                Employee.__table__.insert().values(
                    id=e["id"], name=e["name"],
                    employment_type=e.get("employment_type", "full_time"),
                    sort_order=e.get("sort_order", 0),
                    staff_token=e.get("staff_token"),
                )
            )
        db.flush()

        # Restore employee_job_types
        for ejt in data.get("employee_job_types", []):
            db.execute(
                EmployeeJobType.__table__.insert().values(
                    employee_id=ejt["employee_id"],
                    job_type_id=ejt["job_type_id"],
                )
            )

        # Restore shift_requests
        for sr in data.get("shift_requests", []):
            db.execute(
                ShiftRequest.__table__.insert().values(
                    id=sr["id"],
                    employee_id=sr["employee_id"],
                    target_month=sr["target_month"],
                    requested_work_days=sr.get("requested_work_days"),
                    weekly_work_day_limit=sr.get("weekly_work_day_limit"),
                    note=sr.get("note"),
                )
            )
        db.flush()

        # Restore request_details
        for rd in data.get("request_details", []):
            db.execute(
                RequestDetail.__table__.insert().values(
                    shift_request_id=rd["shift_request_id"],
                    date=date.fromisoformat(rd["date"]),
                    period=rd.get("period", "all_day"),
                )
            )

        # Restore daily_requirements
        for dr in data.get("daily_requirements", []):
            db.execute(
                DailyRequirement.__table__.insert().values(
                    date=date.fromisoformat(dr["date"]),
                    job_type_id=dr["job_type_id"],
                    required_count=dr.get("required_count", 0),
                )
            )

        # Restore company_holidays（キーが無い旧形式バックアップでは既存データを消さない）
        if "company_holidays" in data:
            db.query(CompanyHoliday).delete()
            db.flush()
            for ch in data.get("company_holidays") or []:
                db.execute(
                    CompanyHoliday.__table__.insert().values(
                        date=date.fromisoformat(ch["date"]),
                        name=ch.get("name") or "臨時休業",
                    )
                )

        # Restore kasutori（キーが無い旧形式バックアップでは既存データを消さない）
        if "kasutori_staff" in data:
            db.query(KasutoriAttendance).delete()
            db.query(KasutoriStaff).delete()
            db.flush()
            for s in data.get("kasutori_staff") or []:
                db.execute(
                    KasutoriStaff.__table__.insert().values(
                        id=s["id"], name=s["name"],
                        sort_order=s.get("sort_order", 0),
                        default_weekdays=s.get("default_weekdays", ""),
                    )
                )
            db.flush()
            for a in data.get("kasutori_attendance") or []:
                db.execute(
                    KasutoriAttendance.__table__.insert().values(
                        staff_id=a["staff_id"],
                        date=date.fromisoformat(a["date"]),
                        is_working=a.get("is_working", 0),
                    )
                )

        db.commit()
        return {"detail": "データを復元しました", "restored": {
            "job_types": len(data.get("job_types", [])),
            "employees": len(data.get("employees", [])),
            "shift_requests": len(data.get("shift_requests", [])),
            "daily_requirements": len(data.get("daily_requirements", [])),
            "company_holidays": len(data.get("company_holidays") or []),
            "kasutori_staff": len(data.get("kasutori_staff") or []),
        }}

    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"detail": f"復元エラー: {e}"})
