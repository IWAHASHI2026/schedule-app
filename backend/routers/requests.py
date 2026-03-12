import json
from datetime import date as date_type
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, Employee, ShiftRequest, RequestDetail, RequestBackup
from models import ShiftRequestCreate, ShiftRequestOut, RequestDetailOut, RequestStatusOut

router = APIRouter(prefix="/api/requests", tags=["requests"])


def _request_to_out(req: ShiftRequest) -> ShiftRequestOut:
    return ShiftRequestOut(
        id=req.id,
        employee_id=req.employee_id,
        employee_name=req.employee.name if req.employee else "",
        target_month=req.target_month,
        requested_work_days=str(req.requested_work_days) if req.requested_work_days is not None else None,
        weekly_work_day_limit=req.weekly_work_day_limit,
        note=req.note,
        details=[RequestDetailOut(id=d.id, date=d.date, period=d.period or "all_day") for d in req.details],
    )


@router.get("", response_model=list[ShiftRequestOut])
def list_requests(month: str, db: Session = Depends(get_db)):
    reqs = (
        db.query(ShiftRequest)
        .filter(ShiftRequest.target_month == month)
        .order_by(ShiftRequest.employee_id)
        .all()
    )
    return [_request_to_out(r) for r in reqs]


@router.get("/status", response_model=list[RequestStatusOut])
def request_status(month: str, db: Session = Depends(get_db)):
    employees = db.query(Employee).order_by(Employee.sort_order).all()
    result = []
    for emp in employees:
        has = (
            db.query(ShiftRequest)
            .filter(ShiftRequest.employee_id == emp.id, ShiftRequest.target_month == month)
            .first()
            is not None
        )
        result.append(RequestStatusOut(employee_id=emp.id, employee_name=emp.name, has_request=has))
    return result


@router.get("/{employee_id}", response_model=ShiftRequestOut)
def get_request(employee_id: int, month: str, db: Session = Depends(get_db)):
    req = (
        db.query(ShiftRequest)
        .filter(ShiftRequest.employee_id == employee_id, ShiftRequest.target_month == month)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return _request_to_out(req)


def upsert_shift_request(
    db: Session,
    employee_id: int,
    target_month: str,
    requested_work_days: str | None,
    weekly_work_day_limit: int | None,
    note: str | None,
    days_off: list,
) -> ShiftRequest:
    """Shared upsert logic used by both admin and staff portal endpoints."""
    # Upsert: delete existing for same employee+month
    existing = (
        db.query(ShiftRequest)
        .filter(
            ShiftRequest.employee_id == employee_id,
            ShiftRequest.target_month == target_month,
        )
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    req = ShiftRequest(
        employee_id=employee_id,
        target_month=target_month,
        requested_work_days=requested_work_days,
        weekly_work_day_limit=weekly_work_day_limit,
        note=note,
    )
    db.add(req)
    db.flush()

    for d in days_off:
        db.add(RequestDetail(shift_request_id=req.id, date=d.date, period=d.period))

    db.commit()
    db.refresh(req)
    return req


@router.post("", response_model=ShiftRequestOut, status_code=201)
def upsert_request(body: ShiftRequestCreate, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    req = upsert_shift_request(
        db=db,
        employee_id=body.employee_id,
        target_month=body.target_month,
        requested_work_days=body.requested_work_days,
        weekly_work_day_limit=body.weekly_work_day_limit,
        note=body.note,
        days_off=body.days_off,
    )
    return _request_to_out(req)


@router.post("/clear-all")
def clear_all_requests(body: dict, db: Session = Depends(get_db)):
    """全員の希望休をクリア（バックアップを保存してから削除）。"""
    month = body.get("month")
    if not month:
        raise HTTPException(status_code=400, detail="month is required")

    reqs = (
        db.query(ShiftRequest)
        .filter(ShiftRequest.target_month == month)
        .all()
    )
    if not reqs:
        return {"status": "ok", "cleared": 0}

    # Delete old backups for this month, then save new ones
    db.query(RequestBackup).filter(RequestBackup.target_month == month).delete()

    for req in reqs:
        backup_data = {
            "requested_work_days": req.requested_work_days,
            "weekly_work_day_limit": req.weekly_work_day_limit,
            "note": req.note,
            "details": [
                {"date": d.date.isoformat(), "period": d.period or "all_day"}
                for d in req.details
            ],
        }
        db.add(RequestBackup(
            employee_id=req.employee_id,
            target_month=month,
            backup_data=json.dumps(backup_data, ensure_ascii=False),
        ))
        db.delete(req)

    db.commit()
    return {"status": "ok", "cleared": len(reqs)}


@router.get("/backups", response_model=list[dict])
def list_backups(month: str, db: Session = Depends(get_db)):
    """バックアップがある従業員一覧を返す。"""
    backups = (
        db.query(RequestBackup)
        .filter(RequestBackup.target_month == month)
        .all()
    )
    return [
        {
            "employee_id": b.employee_id,
            "employee_name": b.employee.name if b.employee else "",
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in backups
    ]


@router.post("/{employee_id}/restore", response_model=ShiftRequestOut)
def restore_request(employee_id: int, body: dict, db: Session = Depends(get_db)):
    """バックアップから個別スタッフの希望を復元する。"""
    month = body.get("month")
    if not month:
        raise HTTPException(status_code=400, detail="month is required")

    backup = (
        db.query(RequestBackup)
        .filter(RequestBackup.employee_id == employee_id, RequestBackup.target_month == month)
        .first()
    )
    if not backup:
        raise HTTPException(status_code=404, detail="バックアップが見つかりません")

    data = json.loads(backup.backup_data)

    # Build DayOffItem-like objects for upsert_shift_request
    class _DayOff:
        def __init__(self, date_str: str, period: str):
            self.date = date_type.fromisoformat(date_str)
            self.period = period

    days_off = [_DayOff(d["date"], d["period"]) for d in data.get("details", [])]

    req = upsert_shift_request(
        db=db,
        employee_id=employee_id,
        target_month=month,
        requested_work_days=data.get("requested_work_days"),
        weekly_work_day_limit=data.get("weekly_work_day_limit"),
        note=data.get("note"),
        days_off=days_off,
    )

    # Remove used backup
    db.delete(backup)
    db.commit()

    return _request_to_out(req)
