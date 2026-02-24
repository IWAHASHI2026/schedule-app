from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import (
    get_db, Schedule, ShiftAssignment, NlpModificationLog, Employee, JobType,
)
from models import NlpModifyRequest, NlpModifyResponse, ShiftAssignmentOut, NlpLogOut
from services.nlp_service import parse_modification
from services.optimizer import generate_schedule
import json

router = APIRouter(tags=["nlp_modify"])


@router.post("/api/schedules/{schedule_id}/nlp-modify")
def nlp_modify(schedule_id: int, body: NlpModifyRequest, db: Session = Depends(get_db)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Build current summary for Claude
    assignments = (
        db.query(ShiftAssignment)
        .filter(ShiftAssignment.schedule_id == schedule_id)
        .all()
    )
    employees = db.query(Employee).all()
    job_types = db.query(JobType).all()
    jt_map = {jt.id: jt.name for jt in job_types}

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

    # Parse with Claude
    try:
        parsed = parse_modification(body.input_text, current_summary)
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

    # Re-generate with extra constraints
    try:
        new_schedule_id, new_assignments, violations = generate_schedule(
            db, schedule.target_month, extra_constraints=parsed
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Compute changes (diff)
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
