from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db, DailyRequirement, JobType
from models import DailyRequirementsCreate, DailyRequirementOut, RequirementsTemplate
from routers.holidays import is_non_working_day
from datetime import date, timedelta
import calendar

router = APIRouter(prefix="/api/requirements", tags=["requirements"])


def _req_to_out(r: DailyRequirement) -> DailyRequirementOut:
    return DailyRequirementOut(
        id=r.id,
        date=r.date,
        job_type_id=r.job_type_id,
        job_type_name=r.job_type.name if r.job_type else "",
        required_count=r.required_count,
    )


@router.get("", response_model=list[DailyRequirementOut])
def list_requirements(month: str, db: Session = Depends(get_db)):
    year, mon = map(int, month.split("-"))
    days_in_month = calendar.monthrange(year, mon)[1]
    start = date(year, mon, 1)
    end = date(year, mon, days_in_month)
    reqs = (
        db.query(DailyRequirement)
        .filter(DailyRequirement.date >= start, DailyRequirement.date <= end)
        .order_by(DailyRequirement.date, DailyRequirement.job_type_id)
        .all()
    )
    return [_req_to_out(r) for r in reqs]


@router.post("", status_code=201)
def upsert_requirements(body: DailyRequirementsCreate, db: Session = Depends(get_db)):
    for item in body.items:
        existing = (
            db.query(DailyRequirement)
            .filter(
                DailyRequirement.date == item.date,
                DailyRequirement.job_type_id == item.job_type_id,
            )
            .first()
        )
        if existing:
            existing.required_count = item.required_count
        else:
            db.add(
                DailyRequirement(
                    date=item.date,
                    job_type_id=item.job_type_id,
                    required_count=item.required_count,
                )
            )
    db.commit()
    return {"status": "ok"}


@router.post("/template", status_code=201)
def apply_template(body: RequirementsTemplate, db: Session = Depends(get_db)):
    year, mon = map(int, body.month.split("-"))
    days_in_month = calendar.monthrange(year, mon)[1]

    for day_num in range(1, days_in_month + 1):
        d = date(year, mon, day_num)
        if is_non_working_day(d):
            continue
        weekday = d.weekday()  # 0=Mon
        if weekday not in body.weekday_requirements:
            continue
        for tmpl in body.weekday_requirements[weekday]:
            existing = (
                db.query(DailyRequirement)
                .filter(
                    DailyRequirement.date == d,
                    DailyRequirement.job_type_id == tmpl.job_type_id,
                )
                .first()
            )
            if existing:
                existing.required_count = tmpl.required_count
            else:
                db.add(
                    DailyRequirement(
                        date=d,
                        job_type_id=tmpl.job_type_id,
                        required_count=tmpl.required_count,
                    )
                )
    db.commit()
    return {"status": "ok"}
