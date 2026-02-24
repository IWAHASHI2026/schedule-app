from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, Employee, EmployeeJobType, JobType
from models import EmployeeCreate, EmployeeUpdate, EmployeeOut, EmployeeJobTypesUpdate, JobTypeOut

router = APIRouter(prefix="/api/employees", tags=["employees"])


def _employee_to_out(emp: Employee) -> EmployeeOut:
    return EmployeeOut(
        id=emp.id,
        name=emp.name,
        employment_type=emp.employment_type or "full_time",
        job_types=[
            JobTypeOut(id=ejt.job_type.id, name=ejt.job_type.name, color=ejt.job_type.color)
            for ejt in emp.job_types
        ],
    )


@router.get("", response_model=list[EmployeeOut])
def list_employees(db: Session = Depends(get_db)):
    employees = db.query(Employee).order_by(Employee.id).all()
    return [_employee_to_out(e) for e in employees]


@router.post("", response_model=EmployeeOut, status_code=201)
def create_employee(body: EmployeeCreate, db: Session = Depends(get_db)):
    emp = Employee(name=body.name, employment_type=body.employment_type)
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return _employee_to_out(emp)


@router.put("/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: int, body: EmployeeUpdate, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp.name = body.name
    emp.employment_type = body.employment_type
    db.commit()
    db.refresh(emp)
    return _employee_to_out(emp)


@router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.delete(emp)
    db.commit()


@router.put("/{employee_id}/job-types", response_model=EmployeeOut)
def update_employee_job_types(
    employee_id: int, body: EmployeeJobTypesUpdate, db: Session = Depends(get_db)
):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Delete existing
    db.query(EmployeeJobType).filter(EmployeeJobType.employee_id == employee_id).delete()

    # Insert new
    for jt_id in body.job_type_ids:
        jt = db.query(JobType).filter(JobType.id == jt_id).first()
        if not jt:
            raise HTTPException(status_code=400, detail=f"JobType {jt_id} not found")
        db.add(EmployeeJobType(employee_id=employee_id, job_type_id=jt_id))

    db.commit()
    db.refresh(emp)
    return _employee_to_out(emp)
