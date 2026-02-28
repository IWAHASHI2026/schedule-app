from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import (
    get_db, Schedule, ShiftAssignment, NlpModificationLog, Employee, JobType,
)
from models import NlpModifyRequest, NlpModifyResponse, ShiftAssignmentOut, NlpLogOut
from services.nlp_service import parse_modification
from services.optimizer import generate_schedule
from datetime import datetime
import json

router = APIRouter(tags=["nlp_modify"])


@router.post("/api/schedules/{schedule_id}/nlp-modify")
def nlp_modify(schedule_id: int, body: NlpModifyRequest, db: Session = Depends(get_db)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Build current summary and per-day detail for Claude
    assignments = (
        db.query(ShiftAssignment)
        .filter(ShiftAssignment.schedule_id == schedule_id)
        .all()
    )
    employees = db.query(Employee).all()
    job_types = db.query(JobType).all()
    jt_map = {jt.id: jt.name for jt in job_types}

    # Summary (aggregate counts per employee)
    summary_lines = []
    for emp in employees:
        emp_assignments = [a for a in assignments if a.employee_id == emp.id and a.work_type != "off"]
        jt_counts: dict[str, int] = {}
        for a in emp_assignments:
            jt_name = jt_map.get(a.job_type_id, "不明")
            jt_counts[jt_name] = jt_counts.get(jt_name, 0) + 1
        counts_str = ", ".join(f"{k}: {v}日" for k, v in jt_counts.items())
        summary_lines.append(f"- {emp.name}: 出勤{len(emp_assignments)}日 ({counts_str})")
    current_summary = "\n".join(summary_lines)

    # Per-day detail (e.g. "若生亜紀子: 3/1=休み, 3/2=データ, 3/3=職人, ...")
    detail_lines = []
    for emp in employees:
        emp_assignments = sorted(
            [a for a in assignments if a.employee_id == emp.id],
            key=lambda a: a.date,
        )
        day_parts = []
        for a in emp_assignments:
            if a.work_type == "off" or a.job_type_id is None:
                day_parts.append(f"{a.date.month}/{a.date.day}=休み")
            else:
                jt_name = jt_map.get(a.job_type_id, "不明")
                day_parts.append(f"{a.date.month}/{a.date.day}={jt_name}")
        detail_lines.append(f"- {emp.name}: {', '.join(day_parts)}")
    schedule_detail = "\n".join(detail_lines)

    # Parse with Claude
    try:
        parsed = parse_modification(body.input_text, current_summary, schedule_detail, schedule.target_month)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NLP parsing failed: {str(e)}")

    # Save log
    log = NlpModificationLog(
        schedule_id=schedule_id,
        input_text=body.input_text,
        parsed_instruction=json.dumps(parsed, ensure_ascii=False),
        status="pending",
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    # Split parsed instructions into pin vs adjust
    pin_changes = [p for p in parsed if p.get("type") == "pin"]
    adjust_changes = [p for p in parsed if p.get("type") == "adjust"]

    # If there are only pin changes, apply them directly without re-optimization
    if pin_changes and not adjust_changes:
        new_schedule_id, changes = _apply_pin_changes(
            db, schedule, assignments, pin_changes, jt_map, employees,
        )
        violations = []
    else:
        # Existing flow: re-generate with extra constraints (adjust changes)
        # Also handle mixed: apply pins after re-optimization
        try:
            new_schedule_id, _, violations = generate_schedule(
                db, schedule.target_month, extra_constraints=adjust_changes or parsed
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # If mixed, apply pin changes on top of the re-optimized schedule
        if pin_changes:
            new_assignments_db = (
                db.query(ShiftAssignment)
                .filter(ShiftAssignment.schedule_id == new_schedule_id)
                .all()
            )
            _apply_pins_to_assignments(db, new_assignments_db, pin_changes, jt_map, employees)

        # Compute diff
        old_map = {}
        for a in assignments:
            old_map[(a.employee_id, a.date.isoformat())] = a.job_type_id

        changes = []
        new_assignments_db = (
            db.query(ShiftAssignment)
            .filter(ShiftAssignment.schedule_id == new_schedule_id)
            .all()
        )
        for a in new_assignments_db:
            old_jt = old_map.get((a.employee_id, a.date.isoformat()))
            if old_jt != a.job_type_id:
                old_name = jt_map.get(old_jt, "休み") if old_jt else "休み"
                new_name = jt_map.get(a.job_type_id, "休み") if a.job_type_id else "休み"
                changes.append({
                    "employee_id": a.employee_id,
                    "employee_name": a.employee.name if a.employee else "",
                    "date": a.date.isoformat(),
                    "old_job_type": old_name,
                    "new_job_type": new_name,
                })

    # Update log with new schedule reference
    log.parsed_instruction = json.dumps({
        "constraints": parsed,
        "new_schedule_id": new_schedule_id,
        "changes_count": len(changes),
    }, ensure_ascii=False)
    db.commit()

    return {
        "log_id": log.id,
        "new_schedule_id": new_schedule_id,
        "parsed_instruction": parsed,
        "changes": changes,
        "violations": violations,
    }


def _apply_pin_changes(
    db: Session,
    old_schedule: Schedule,
    old_assignments: list[ShiftAssignment],
    pin_changes: list[dict],
    jt_map: dict[int, str],
    employees: list[Employee],
) -> tuple[int, list[dict]]:
    """
    Apply pin (date-specific) changes by copying the old schedule and modifying
    only the pinned cells. Returns (new_schedule_id, changes_list).
    """
    # Build reverse maps
    jt_name_to_id = {name: id_ for id_, name in jt_map.items()}
    emp_name_to_id = {emp.name: emp.id for emp in employees}

    # Create new schedule
    new_schedule = Schedule(
        target_month=old_schedule.target_month,
        status="draft",
        generated_at=datetime.utcnow(),
    )
    db.add(new_schedule)
    db.flush()  # get new_schedule.id

    # Copy all assignments from old schedule to new schedule
    old_map: dict[tuple[int, str], ShiftAssignment] = {}
    for a in old_assignments:
        old_map[(a.employee_id, a.date.isoformat())] = a
        new_a = ShiftAssignment(
            schedule_id=new_schedule.id,
            employee_id=a.employee_id,
            date=a.date,
            job_type_id=a.job_type_id,
            work_type=a.work_type,
            headcount_value=a.headcount_value,
        )
        db.add(new_a)
    db.flush()

    # Load new assignments for modification
    new_assignments = (
        db.query(ShiftAssignment)
        .filter(ShiftAssignment.schedule_id == new_schedule.id)
        .all()
    )
    _apply_pins_to_assignments(db, new_assignments, pin_changes, jt_map, employees)

    # Compute diff
    changes = []
    new_assignments = (
        db.query(ShiftAssignment)
        .filter(ShiftAssignment.schedule_id == new_schedule.id)
        .all()
    )
    for a in new_assignments:
        old_a = old_map.get((a.employee_id, a.date.isoformat()))
        old_jt = old_a.job_type_id if old_a else None
        if old_jt != a.job_type_id:
            old_name = jt_map.get(old_jt, "休み") if old_jt else "休み"
            new_name = jt_map.get(a.job_type_id, "休み") if a.job_type_id else "休み"
            changes.append({
                "employee_id": a.employee_id,
                "employee_name": a.employee.name if a.employee else "",
                "date": a.date.isoformat(),
                "old_job_type": old_name,
                "new_job_type": new_name,
            })

    db.commit()
    return new_schedule.id, changes


def _apply_pins_to_assignments(
    db: Session,
    assignments: list[ShiftAssignment],
    pin_changes: list[dict],
    jt_map: dict[int, str],
    employees: list[Employee],
) -> None:
    """Mutate assignment records in-place based on pin changes."""
    jt_name_to_id = {name: id_ for id_, name in jt_map.items()}
    emp_name_to_id = {emp.name: emp.id for emp in employees}

    # Index assignments by (employee_id, date_iso)
    assign_map: dict[tuple[int, str], ShiftAssignment] = {}
    for a in assignments:
        assign_map[(a.employee_id, a.date.isoformat())] = a

    for pin in pin_changes:
        emp_id = emp_name_to_id.get(pin.get("employee_name", ""))
        date_str = pin.get("date", "")
        new_jt_name = pin.get("new_job_type", "")

        if not emp_id or not date_str:
            continue

        target = assign_map.get((emp_id, date_str))
        if not target:
            continue

        if new_jt_name == "休み":
            target.job_type_id = None
            target.work_type = "off"
            target.headcount_value = 0
        else:
            jt_id = jt_name_to_id.get(new_jt_name)
            if jt_id is not None:
                target.job_type_id = jt_id
                target.work_type = "full"
                target.headcount_value = 1.0

    db.flush()


@router.put("/api/nlp-logs/{log_id}/approve")
def approve_log(log_id: int, db: Session = Depends(get_db)):
    log = db.query(NlpModificationLog).filter(NlpModificationLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    log.status = "approved"
    db.commit()
    return {"status": "ok"}


@router.put("/api/nlp-logs/{log_id}/reject")
def reject_log(log_id: int, db: Session = Depends(get_db)):
    log = db.query(NlpModificationLog).filter(NlpModificationLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")

    # Delete the new schedule that was generated
    parsed = json.loads(log.parsed_instruction) if log.parsed_instruction else {}
    new_schedule_id = parsed.get("new_schedule_id")
    if new_schedule_id:
        new_schedule = db.query(Schedule).filter(Schedule.id == new_schedule_id).first()
        if new_schedule:
            db.delete(new_schedule)

    log.status = "rejected"
    db.commit()
    return {"status": "ok"}
