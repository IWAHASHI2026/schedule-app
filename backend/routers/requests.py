from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, Employee, ShiftRequest, RequestDetail
from models import ShiftRequestCreate, ShiftRequestOut, RequestDetailOut, RequestStatusOut

router = APIRouter(prefix="/api/requests", tags=["requests"])


def _request_to_out(req: ShiftRequest) -> ShiftRequestOut:
    return ShiftRequestOut(
        id=req.id,
        employee_id=req.employee_id,
        employee_name=req.employee.name if req.employee else "",
        target_month=req.target_month,
        requested_work_days=req.requested_work_days,
        requested_days_off=req.requested_days_off,
        note=req.note,
        details=[RequestDetailOut(id=d.id, date=d.date) for d in req.details],
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
    employees = db.query(Employee).order_by(Employee.id).all()
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


@router.post("", response_model=ShiftRequestOut, status_code=201)
def upsert_request(body: ShiftRequestCreate, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Upsert: delete existing for same employee+month
    existing = (
        db.query(ShiftRequest)
        .filter(
            ShiftRequest.employee_id == body.employee_id,
            ShiftRequest.target_month == body.target_month,
        )
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    req = ShiftRequest(
        employee_id=body.employee_id,
        target_month=body.target_month,
        requested_work_days=body.requested_work_days,
        requested_days_off=body.requested_days_off,
        note=body.note,
    )
    db.add(req)
    db.flush()

    for d in body.days_off:
        db.add(RequestDetail(shift_request_id=req.id, date=d))

    db.commit()
    db.refresh(req)
    return _request_to_out(req)
