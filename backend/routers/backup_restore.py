"""Full database backup and restore API.

管理者が全データを JSON で取り出し、同じデータベースや新しいデータベースに書き戻せる。
バックアップには、生成済みのシフト（schedules / shift_assignments）も含める。
"""

from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session
from database import (
    get_db, Employee, EmployeeJobType, JobType,
    ShiftRequest, RequestDetail, DailyRequirement,
    Schedule, ShiftAssignment, NlpModificationLog, CompanyHoliday,
    KasutoriStaff, KasutoriAttendance, _is_sqlite,
)
from datetime import date, datetime
import json

router = APIRouter(prefix="/api/backup", tags=["backup"])

# 復元時に元の id のまま書き戻すテーブル。PostgreSQL では自動採番がこの id を
# 知らないため、復元後に採番を進める（_advance_sequences）。
TABLES_WITH_EXPLICIT_IDS = ("job_types", "employees", "shift_requests", "schedules", "kasutori_staff")


def _serialize_date(obj):
    """JSON serializer for date/datetime objects."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def _parse_date(value):
    return date.fromisoformat(value) if value else None


def _parse_datetime(value):
    return datetime.fromisoformat(value) if value else None


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
                "retired_at": e.retired_at.isoformat() if e.retired_at else None,
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
        # 生成済みのシフト（状態・コメント・割当）
        "schedules": [
            {
                "id": s.id,
                "target_month": s.target_month,
                "status": s.status,
                "generated_at": s.generated_at.isoformat() if s.generated_at else None,
                "confirmed_at": s.confirmed_at.isoformat() if s.confirmed_at else None,
                "comment": s.comment or "",
            }
            for s in db.query(Schedule).order_by(Schedule.id).all()
        ],
        "shift_assignments": [
            {
                "schedule_id": a.schedule_id,
                "employee_id": a.employee_id,
                "date": a.date.isoformat(),
                "job_type_id": a.job_type_id,
                "work_type": a.work_type,
                "headcount_value": a.headcount_value,
            }
            for a in db.query(ShiftAssignment).order_by(ShiftAssignment.schedule_id, ShiftAssignment.id).all()
        ],
    }
    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": "attachment; filename=shift_backup.json"
        },
    )


def _advance_sequences(db: Session) -> None:
    """id を指定して書き戻したテーブルの自動採番を、現在の最大 id の次まで進める。

    PostgreSQL の自動採番は、id を指定した INSERT では進まない。新しいデータベースに
    復元したあと、そのままスタッフ追加や希望の送信をすると、既存の id と重複して失敗する。
    SQLite は最大 id の次を自動で使うため不要。
    """
    if _is_sqlite:
        return
    for table in TABLES_WITH_EXPLICIT_IDS:
        db.execute(sa_text(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
            f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)"
        ))


@router.post("/restore")
async def restore_backup(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Restore all data from a JSON backup file.

    - 職種・スタッフは id を保ったまま上書きする（削除して入れ直すと、シフト割当が
      カスケードで消えてしまうため）。バックアップに無いスタッフは削除する。
    - 担当職種・希望・必要人数は全部入れ替える。
    - 休業日・カス取り・シフトは、バックアップにそのキーがあるときだけ入れ替える
      （旧形式のバックアップで既存データを消さない）。
    """
    try:
        content = await file.read()
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return JSONResponse(status_code=400, content={"detail": f"Invalid JSON: {e}"})

    try:
        # ---- 職種: id で上書き・追加（削除はしない。割当が参照しているため）
        for jt in data.get("job_types", []):
            row = db.get(JobType, jt["id"])
            if row:
                row.name = jt["name"]
                row.color = jt.get("color")
                row.sort_order = jt.get("sort_order", 0)
            else:
                db.execute(
                    JobType.__table__.insert().values(
                        id=jt["id"], name=jt["name"],
                        color=jt.get("color"), sort_order=jt.get("sort_order", 0),
                    )
                )
        db.flush()

        # ---- スタッフ: バックアップに無い人は削除（割当・希望も消える）
        backup_emp_ids = {e["id"] for e in data.get("employees", [])}
        for row in db.query(Employee).all():
            if row.id not in backup_emp_ids:
                db.delete(row)
        db.flush()
        # 同じトークンを別の人に付け直す場合に重複で失敗しないよう、先に全員分を外す
        db.query(Employee).update({Employee.staff_token: None})
        db.flush()
        for e in data.get("employees", []):
            values = dict(
                name=e["name"],
                employment_type=e.get("employment_type", "full_time"),
                sort_order=e.get("sort_order", 0),
                staff_token=e.get("staff_token"),
                retired_at=_parse_date(e.get("retired_at")),
            )
            row = db.get(Employee, e["id"])
            if row:
                for k, v in values.items():
                    setattr(row, k, v)
            else:
                db.execute(Employee.__table__.insert().values(id=e["id"], **values))
        db.flush()

        # ---- 担当職種・希望・必要人数: 全部入れ替え
        db.query(EmployeeJobType).delete()
        db.query(RequestDetail).delete()
        db.query(ShiftRequest).delete()
        db.query(DailyRequirement).delete()
        db.flush()

        for ejt in data.get("employee_job_types", []):
            db.execute(
                EmployeeJobType.__table__.insert().values(
                    employee_id=ejt["employee_id"],
                    job_type_id=ejt["job_type_id"],
                )
            )
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
        for rd in data.get("request_details", []):
            db.execute(
                RequestDetail.__table__.insert().values(
                    shift_request_id=rd["shift_request_id"],
                    date=date.fromisoformat(rd["date"]),
                    period=rd.get("period", "all_day"),
                )
            )
        for dr in data.get("daily_requirements", []):
            db.execute(
                DailyRequirement.__table__.insert().values(
                    date=date.fromisoformat(dr["date"]),
                    job_type_id=dr["job_type_id"],
                    required_count=dr.get("required_count", 0),
                )
            )

        # ---- 休業日（キーが無い旧形式バックアップでは既存データを消さない）
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

        # ---- カス取り（同上）
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

        # ---- 生成済みシフト（同上。キーが無ければ既存のシフトはそのまま残す）
        if "schedules" in data:
            db.query(NlpModificationLog).delete()
            db.query(ShiftAssignment).delete()
            db.query(Schedule).delete()
            db.flush()
            for s in data.get("schedules") or []:
                db.execute(
                    Schedule.__table__.insert().values(
                        id=s["id"],
                        target_month=s["target_month"],
                        status=s.get("status", "draft"),
                        generated_at=_parse_datetime(s.get("generated_at")),
                        confirmed_at=_parse_datetime(s.get("confirmed_at")),
                        comment=s.get("comment") or "",
                    )
                )
            db.flush()
            valid_emp_ids = {e.id for e in db.query(Employee.id).all()}
            for a in data.get("shift_assignments") or []:
                if a["employee_id"] not in valid_emp_ids:
                    continue  # バックアップ内で整合しない行は飛ばす
                db.execute(
                    ShiftAssignment.__table__.insert().values(
                        schedule_id=a["schedule_id"],
                        employee_id=a["employee_id"],
                        date=date.fromisoformat(a["date"]),
                        job_type_id=a.get("job_type_id"),
                        work_type=a.get("work_type", "full"),
                        headcount_value=a.get("headcount_value", 1.0),
                    )
                )

        _advance_sequences(db)
        db.commit()
        return {"detail": "データを復元しました", "restored": {
            "job_types": len(data.get("job_types", [])),
            "employees": len(data.get("employees", [])),
            "shift_requests": len(data.get("shift_requests", [])),
            "daily_requirements": len(data.get("daily_requirements", [])),
            "company_holidays": len(data.get("company_holidays") or []),
            "kasutori_staff": len(data.get("kasutori_staff") or []),
            "schedules": len(data.get("schedules") or []) if "schedules" in data else None,
        }}

    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"detail": f"復元エラー: {e}"})
