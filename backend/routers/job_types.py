from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db, JobType
from models import JobTypeOut

router = APIRouter(prefix="/api/job-types", tags=["job_types"])


@router.get("", response_model=list[JobTypeOut])
def list_job_types(db: Session = Depends(get_db)):
    return [
        JobTypeOut(id=jt.id, name=jt.name, color=jt.color)
        for jt in db.query(JobType).order_by(JobType.id).all()
    ]
