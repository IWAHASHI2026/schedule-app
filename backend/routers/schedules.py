from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, Schedule, ShiftAssignment, Employee, JobType
from models import (
    ScheduleOut, ShiftAssignmentOut, ShiftAssignmentUpdate,
    ScheduleGenerate, StatusUpdate,
)
from services.optimizer import generate_schedule
from datetime import datetime

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def _assignment_to_out(a: ShiftAssignment) -> ShiftAssignmentOut:
    return ShiftAssignmentOut(
        id=a.id,
        schedule_id=a.schedule_id,
        employee_id=a.employee_id,
        employee_name=a.employee.name if a.employee else "",
        date=a.date,
        job_type_id=a.job_type_id,
        job_type_name=a.job_type.name if a.job_type else None,
        job_type_color=a.job_type.color if a.job_type else None,
        work_type=a.work_type,
        headcount_value=a.headcount_value,
    )


@router.get("", response_model=list[ScheduleOut])
def list_schedules(month: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Schedule)
    if month:
        q = q.filter(Schedule.target_month == month)
    schedules = q.order_by(Schedule.id.desc()).all()
    return [
        ScheduleOut(
            id=s.id,
            target_month=s.target_month,
            status=s.status,
            generated_at=s.generated_at.isoformat() if s.generated_at else None,
            confirmed_at=s.confirmed_at.isoformat() if s.confirmed_at else None,
        )
        for s in schedules
    ]


@router.post("/generate")
def generate(body: ScheduleGenerate, db: Session = Depends(get_db)):
    try:
        schedule_id, assignments, violations = generate_schedule(db, body.month)
        return {
            "schedule_id": schedule_id,
            "assignment_count": len(assignments),
            "violations": violations,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{schedule_id}/assignments", response_model=list[ShiftAssignmentOut])
def get_assignments(schedule_id: int, db: Session = Depends(get_db)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    assignments = (
        db.query(ShiftAssignment)
        .filter(ShiftAssignment.schedule_id == schedule_id)
        .order_by(ShiftAssignment.employee_id, ShiftAssignment.date)
        .all()
    )
    return [_assignment_to_out(a) for a in assignments]


@router.put("/{schedule_id}/assignments")
def update_assignments(
    schedule_id: int, body: list[ShiftAssignmentUpdate], db: Session = Depends(get_db)
):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    for item in body:
        existing = (
            db.query(ShiftAssignment)
            .filter(
                ShiftAssignment.schedule_id == schedule_id,
                ShiftAssignment.employee_id == item.employee_id,
                ShiftAssignment.date == item.date,
            )
            .first()
        )
        if existing:
            existing.job_type_id = item.job_type_id
            existing.work_type = item.work_type
            if item.work_type == "off":
                existing.headcount_value = 0
            elif item.work_type in ("morning_half", "afternoon_half"):
                existing.headcount_value = 0.5
            else:
                existing.headcount_value = 1.0

    db.commit()
    return {"status": "ok"}


@router.put("/{schedule_id}/status")
def update_status(schedule_id: int, body: StatusUpdate, db: Session = Depends(get_db)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if body.status not in ("draft", "preview", "confirmed", "published"):
        raise HTTPException(status_code=400, detail="Invalid status")

    schedule.status = body.status
    if body.status == "confirmed":
        schedule.confirmed_at = datetime.utcnow()
    db.commit()
    return {"status": "ok"}
