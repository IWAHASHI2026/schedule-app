from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, Employee, ShiftRequest
from models import StaffPortalInfo, StaffRequestSubmit, ShiftRequestOut
from routers.requests import upsert_shift_request, _request_to_out

router = APIRouter(prefix="/api/staff-portal", tags=["staff-portal"])


def _get_employee_by_token(db: Session, token: str) -> Employee:
    emp = db.query(Employee).filter(Employee.staff_token == token).first()
    if not emp:
        raise HTTPException(status_code=404, detail="無効なリンクです")
    return emp


@router.get("/{token}", response_model=StaffPortalInfo)
def get_staff_portal_info(token: str, month: str, db: Session = Depends(get_db)):
    emp = _get_employee_by_token(db, token)

    existing_request = None
    req = (
        db.query(ShiftRequest)
        .filter(ShiftRequest.employee_id == emp.id, ShiftRequest.target_month == month)
        .first()
    )
    if req:
        existing_request = _request_to_out(req)

    return StaffPortalInfo(
        employee_id=emp.id,
        employee_name=emp.name,
        employment_type=emp.employment_type or "full_time",
        target_month=month,
        existing_request=existing_request,
    )


@router.post("/{token}", response_model=ShiftRequestOut, status_code=201)
def submit_staff_request(token: str, body: StaffRequestSubmit, db: Session = Depends(get_db)):
    emp = _get_employee_by_token(db, token)

    existing = (
        db.query(ShiftRequest)
        .filter(ShiftRequest.employee_id == emp.id, ShiftRequest.target_month == body.target_month)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="既にシフト希望が送信済みです。変更が必要な場合は管理者にご連絡ください。")

    req = upsert_shift_request(
        db=db,
        employee_id=emp.id,
        target_month=body.target_month,
        requested_work_days=body.requested_work_days,
        weekly_work_day_limit=body.weekly_work_day_limit,
        note=body.note,
        days_off=body.days_off,
    )
    return _request_to_out(req)
