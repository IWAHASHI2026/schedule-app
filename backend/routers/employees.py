import uuid
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db, Employee, EmployeeJobType, JobType, ShiftAssignment
from models import (
    EmployeeCreate, EmployeeUpdate, EmployeeOut, EmployeeJobTypesUpdate, EmployeeFullUpdate,
    EmployeeReorder, EmployeeRetireUpdate, EmployeeTokenOut, JobTypeOut,
)

router = APIRouter(prefix="/api/employees", tags=["employees"])


def _employee_to_out(emp: Employee) -> EmployeeOut:
    return EmployeeOut(
        id=emp.id,
        name=emp.name,
        employment_type=emp.employment_type or "full_time",
        sort_order=emp.sort_order,
        job_types=[
            JobTypeOut(id=ejt.job_type.id, name=ejt.job_type.name, color=ejt.job_type.color)
            for ejt in sorted(emp.job_types, key=lambda ejt: ejt.job_type.sort_order)
        ],
        retired_at=emp.retired_at,
    )


@router.get("", response_model=list[EmployeeOut])
def list_employees(db: Session = Depends(get_db)):
    employees = db.query(Employee).order_by(Employee.sort_order).all()
    return [_employee_to_out(e) for e in employees]


@router.post("", response_model=EmployeeOut, status_code=201)
def create_employee(body: EmployeeCreate, db: Session = Depends(get_db)):
    max_order = db.query(func.max(Employee.sort_order)).scalar() or 0
    emp = Employee(name=body.name, employment_type=body.employment_type, sort_order=max_order + 1)
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return _employee_to_out(emp)


@router.put("/reorder", response_model=list[EmployeeOut])
def reorder_employees(body: EmployeeReorder, db: Session = Depends(get_db)):
    """スタッフの表示順を一括更新する。"""
    for idx, emp_id in enumerate(body.employee_ids):
        emp = db.query(Employee).filter(Employee.id == emp_id).first()
        if emp:
            emp.sort_order = idx
    db.commit()
    employees = db.query(Employee).order_by(Employee.sort_order).all()
    return [_employee_to_out(e) for e in employees]


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
    # 削除は過去のシフト割当も一緒に消す（カスケード）。シフトに載ったことがある
    # スタッフは記録を残すため削除できない。退職にする
    has_history = (
        db.query(ShiftAssignment.id)
        .filter(ShiftAssignment.employee_id == employee_id)
        .first()
        is not None
    )
    if has_history:
        raise HTTPException(
            status_code=400,
            detail="過去のシフトに載っているため削除できません。「退職」にしてください（シフト生成の対象から外れ、過去のシフトはそのまま残ります）。",
        )
    db.delete(emp)
    db.commit()


@router.put("/{employee_id}/retire", response_model=EmployeeOut)
def set_employee_retired(
    employee_id: int, body: EmployeeRetireUpdate, db: Session = Depends(get_db)
):
    """退職 / 復帰を切り替える。退職中はシフト生成・希望入力の対象外になる。"""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp.retired_at = date.today() if body.retired else None
    db.commit()
    db.refresh(emp)
    return _employee_to_out(emp)


@router.put("/{employee_id}/full", response_model=EmployeeOut)
def update_employee_full(
    employee_id: int, body: EmployeeFullUpdate, db: Session = Depends(get_db)
):
    """属性・担当可能な仕事種類を1トランザクションで一括保存する。"""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    emp.name = body.name
    emp.employment_type = body.employment_type

    # Delete existing job types
    db.query(EmployeeJobType).filter(EmployeeJobType.employee_id == employee_id).delete()

    # Insert new job types
    for jt_id in body.job_type_ids:
        jt = db.query(JobType).filter(JobType.id == jt_id).first()
        if not jt:
            raise HTTPException(status_code=400, detail=f"JobType {jt_id} not found")
        db.add(EmployeeJobType(employee_id=employee_id, job_type_id=jt_id))

    db.commit()
    db.refresh(emp)
    return _employee_to_out(emp)


@router.get("/tokens", response_model=list[EmployeeTokenOut])
def list_employee_tokens(db: Session = Depends(get_db)):
    # 退職者には希望入力リンクを出さない
    employees = (
        db.query(Employee)
        .filter(Employee.retired_at.is_(None))
        .order_by(Employee.sort_order)
        .all()
    )
    return [
        EmployeeTokenOut(
            employee_id=emp.id,
            employee_name=emp.name,
            staff_token=emp.staff_token,
        )
        for emp in employees
    ]


@router.post("/{employee_id}/token", response_model=EmployeeTokenOut)
def generate_token(employee_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp.staff_token = str(uuid.uuid4())
    db.commit()
    db.refresh(emp)
    return EmployeeTokenOut(
        employee_id=emp.id,
        employee_name=emp.name,
        staff_token=emp.staff_token,
    )


@router.delete("/{employee_id}/token", status_code=204)
def revoke_token(employee_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp.staff_token = None
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
