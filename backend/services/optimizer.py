"""
Shift scheduling optimizer using Google OR-Tools CP-SAT solver.

Hard constraints:
  HC-01: Requested days off are always respected
         - Full day off (am+pm): employee cannot work
         - Half day off (am or pm only): employee can work with headcount 0.5
  HC-02: One job type per employee per day
  HC-03: Daily required headcount per job type must be met (soft for データ/その他)
  HC-04: Only assign job types the employee is qualified for
  HC-05: No work on weekends/holidays
  HC-06: 職人・サブ職人 are each assigned exactly 1 person per working day
         (half-day workers are excluded from these roles)

Soft constraints (objective function):
  SC-01: Minimize deviation from requested work days (weight 10)
       - "max" = maximize work days (penalize non-work)
       - Half day counts as 0.5 work days
  SC-03: Minimize unfairness in work days across employees (weight 5)
  SC-04: Minimize job type imbalance per employee (weight 1)
  SC-05: Prefer higher-priority job types (lower ID = higher priority, weight 2)
"""

from ortools.sat.python import cp_model
from sqlalchemy.orm import Session
from database import (
    Employee, EmployeeJobType, ShiftRequest, RequestDetail,
    DailyRequirement, Schedule, ShiftAssignment,
)
from routers.holidays import is_non_working_day
from datetime import date, timedelta
import calendar


def generate_schedule(
    db: Session,
    month: str,
    extra_constraints: list[dict] | None = None,
) -> tuple[int, list[dict], list[str]]:
    """
    Generate an optimized shift schedule.

    Returns: (schedule_id, assignments_list, violations_list)
    """
    year, mon = map(int, month.split("-"))
    days_in_month = calendar.monthrange(year, mon)[1]
    all_dates = [date(year, mon, d) for d in range(1, days_in_month + 1)]
    working_dates = [d for d in all_dates if not is_non_working_day(d)]

    # Load data
    employees = db.query(Employee).order_by(Employee.sort_order).all()
    if not employees:
        raise ValueError("No employees registered")

    emp_ids = [e.id for e in employees]
    emp_names = {e.id: e.name for e in employees}

    # Employee -> allowed job type ids
    emp_job_types: dict[int, list[int]] = {}
    for e in employees:
        ejts = db.query(EmployeeJobType).filter(EmployeeJobType.employee_id == e.id).all()
        emp_job_types[e.id] = [ejt.job_type_id for ejt in ejts]

    # All job type ids used in requirements
    all_job_type_ids = sorted(
        set(jt_id for jts in emp_job_types.values() for jt_id in jts)
    )
    if not all_job_type_ids:
        raise ValueError("No job types assigned to any employee")

    # Requested days off per employee (with period info)
    emp_off_periods: dict[int, dict[date, set[str]]] = {}  # e_id -> date -> {"am","pm"}
    emp_requested_work: dict[int, str | None] = {}  # "1"-"23" or "max" or None

    for e_id in emp_ids:
        req = (
            db.query(ShiftRequest)
            .filter(ShiftRequest.employee_id == e_id, ShiftRequest.target_month == month)
            .first()
        )
        if req:
            details = db.query(RequestDetail).filter(RequestDetail.shift_request_id == req.id).all()
            off_periods: dict[date, set[str]] = {}
            for d in details:
                if d.date not in off_periods:
                    off_periods[d.date] = set()
                if d.period == "all_day":
                    off_periods[d.date].update({"am", "pm"})
                else:
                    off_periods[d.date].add(d.period)
            emp_off_periods[e_id] = off_periods
            emp_requested_work[e_id] = str(req.requested_work_days) if req.requested_work_days is not None else None
        else:
            emp_off_periods[e_id] = {}
            emp_requested_work[e_id] = None

    # Derive full-day off set and half-day headcount factor
    emp_full_off: dict[int, set[date]] = {}  # dates with both am+pm off
    emp_half_off: dict[int, dict[date, str]] = {}  # date -> which period is off ("am" or "pm")
    emp_hc_factor: dict[int, dict[date, int]] = {}  # date -> 2 (full) or 1 (half day)

    for e_id in emp_ids:
        emp_full_off[e_id] = set()
        emp_half_off[e_id] = {}
        emp_hc_factor[e_id] = {}
        for d, periods in emp_off_periods[e_id].items():
            if "am" in periods and "pm" in periods:
                emp_full_off[e_id].add(d)
            elif "am" in periods:
                emp_half_off[e_id][d] = "am"
                emp_hc_factor[e_id][d] = 1  # half-day work
            elif "pm" in periods:
                emp_half_off[e_id][d] = "pm"
                emp_hc_factor[e_id][d] = 1  # half-day work

    # Daily requirements: date -> job_type_id -> required_count
    daily_reqs: dict[date, dict[int, float]] = {}
    start_date = date(year, mon, 1)
    end_date = date(year, mon, days_in_month)
    db_reqs = (
        db.query(DailyRequirement)
        .filter(DailyRequirement.date >= start_date, DailyRequirement.date <= end_date)
        .all()
    )
    for dr in db_reqs:
        if dr.date not in daily_reqs:
            daily_reqs[dr.date] = {}
        daily_reqs[dr.date][dr.job_type_id] = dr.required_count

    # ---- Build CP-SAT Model ----
    model = cp_model.CpModel()

    # Decision variables: x[e, d, j] = 1 if employee e works on date d doing job j (full day)
    # For simplicity, we model full-day assignments first
    x = {}
    for e_id in emp_ids:
        for d in working_dates:
            for j in all_job_type_ids:
                x[e_id, d, j] = model.new_bool_var(f"x_{e_id}_{d}_{j}")

    # work[e, d] = 1 if employee e works on date d (any job)
    work = {}
    for e_id in emp_ids:
        for d in working_dates:
            work[e_id, d] = model.new_bool_var(f"work_{e_id}_{d}")

    # Link work to x
    for e_id in emp_ids:
        for d in working_dates:
            model.add(work[e_id, d] == sum(x[e_id, d, j] for j in all_job_type_ids))

    # HC-01: Requested days off -> must not work (full day off only)
    # Half-day off: employee can still work (headcount 0.5) — handled via emp_hc_factor
    for e_id in emp_ids:
        for d in working_dates:
            if d in emp_full_off[e_id]:
                model.add(work[e_id, d] == 0)

    # HC-02: At most one job type per day (already implied by work = sum(x))
    for e_id in emp_ids:
        for d in working_dates:
            model.add(sum(x[e_id, d, j] for j in all_job_type_ids) <= 1)

    # HC-04: Only assign qualified job types
    for e_id in emp_ids:
        allowed = emp_job_types.get(e_id, [])
        for d in working_dates:
            for j in all_job_type_ids:
                if j not in allowed:
                    model.add(x[e_id, d, j] == 0)

    # HC-06: 職人・サブ職人は各営業日に必ず1名ずつ配置（ハード制約）
    # 半日勤務者はフル勤務できないため、職人/サブ職人には割り当てない
    from database import JobType
    hard_one_jt_ids = set()
    for jt in db.query(JobType).filter(JobType.name.in_(["職人", "サブ職人"])).all():
        hard_one_jt_ids.add(jt.id)
    for d in working_dates:
        for j in hard_one_jt_ids:
            if j in all_job_type_ids:
                # 半日勤務者はこの職種に割り当てない
                for e_id in emp_ids:
                    if d in emp_half_off[e_id] and j in emp_job_types.get(e_id, []):
                        model.add(x[e_id, d, j] == 0)
                model.add(
                    sum(x[e_id, d, j] for e_id in emp_ids if j in emp_job_types.get(e_id, [])) == 1
                )

    # HC-03: Meet daily requirements (soft constraint with high penalty)
    # Using integer scaling: multiply by 2 for 0.5 support
    # Half-day workers contribute 1 unit (0.5), full-day workers contribute 2 units (1.0)
    violations = []
    shortage_vars = []  # Track shortages for objective penalty
    for d in working_dates:
        if d not in daily_reqs:
            continue
        for j, req_count in daily_reqs[d].items():
            if j in hard_one_jt_ids:
                continue  # Already enforced as hard constraint above
            scaled_req = int(req_count * 2)
            supply = sum(
                x[e_id, d, j] * emp_hc_factor[e_id].get(d, 2)
                for e_id in emp_ids
                if j in emp_job_types.get(e_id, [])
            )
            # Soft constraint: allow shortage but penalize heavily
            shortage = model.new_int_var(0, scaled_req, f"shortage_{d}_{j}")
            model.add(supply + shortage >= scaled_req)
            shortage_vars.append(shortage)

    # Apply extra constraints from NLP modifications
    if extra_constraints:
        for c in extra_constraints:
            _apply_extra_constraint(model, x, work, c, emp_ids, emp_names,
                                    working_dates, all_job_type_ids, emp_job_types, db)

    # ---- Soft constraints via objective ----
    total_working_dates = len(working_dates)

    # Total work days per employee (scaled by 2: full day=2, half day=1)
    scaled_total = total_working_dates * 2
    emp_total_work = {}
    for e_id in emp_ids:
        emp_total_work[e_id] = model.new_int_var(0, scaled_total, f"tw_{e_id}")
        model.add(
            emp_total_work[e_id] == sum(
                work[e_id, d] * emp_hc_factor[e_id].get(d, 2) for d in working_dates
            )
        )

    objective_terms = []

    # SC-01: Deviation from requested work days (scaled by 2)
    for e_id in emp_ids:
        rw = emp_requested_work.get(e_id)
        if rw == "max":
            # Maximize work days: penalize non-working days
            not_work_count = model.new_int_var(0, scaled_total, f"not_work_{e_id}")
            model.add(not_work_count == scaled_total - emp_total_work[e_id])
            objective_terms.append(not_work_count * 10)
        elif rw is not None:
            # Target specific number of work days (scaled by 2)
            target = int(rw) * 2
            dev = model.new_int_var(0, scaled_total, f"dev_work_{e_id}")
            model.add(dev >= emp_total_work[e_id] - target)
            model.add(dev >= target - emp_total_work[e_id])
            objective_terms.append(dev * 10)

    # SC-03: Fairness - minimize max - min work days (scaled by 2)
    if len(emp_ids) > 1:
        max_work = model.new_int_var(0, scaled_total, "max_work")
        min_work = model.new_int_var(0, scaled_total, "min_work")
        model.add_max_equality(max_work, [emp_total_work[e_id] for e_id in emp_ids])
        model.add_min_equality(min_work, [emp_total_work[e_id] for e_id in emp_ids])
        fairness_diff = model.new_int_var(0, scaled_total, "fairness_diff")
        model.add(fairness_diff == max_work - min_work)
        objective_terms.append(fairness_diff * 5)

    # SC-04: Job type balance per employee
    for e_id in emp_ids:
        allowed = emp_job_types.get(e_id, [])
        if len(allowed) <= 1:
            continue
        job_counts = []
        for j in allowed:
            jc = model.new_int_var(0, total_working_dates, f"jc_{e_id}_{j}")
            model.add(jc == sum(x[e_id, d, j] for d in working_dates))
            job_counts.append(jc)
        # Minimize max - min among job counts
        if len(job_counts) >= 2:
            max_jc = model.new_int_var(0, total_working_dates, f"max_jc_{e_id}")
            min_jc = model.new_int_var(0, total_working_dates, f"min_jc_{e_id}")
            model.add_max_equality(max_jc, job_counts)
            model.add_min_equality(min_jc, job_counts)
            jc_diff = model.new_int_var(0, total_working_dates, f"jc_diff_{e_id}")
            model.add(jc_diff == max_jc - min_jc)
            objective_terms.append(jc_diff * 1)

    # SC-05: Priority cost - prefer lower job_type_id (1=職人, 2=サブ, 3=データ, 4=その他)
    priority_weight = 2
    for e_id in emp_ids:
        for d in working_dates:
            for j in all_job_type_ids:
                objective_terms.append(x[e_id, d, j] * j * priority_weight)

    # Penalty for requirement shortages (very high weight to prioritize meeting requirements)
    for sv in shortage_vars:
        objective_terms.append(sv * 100)

    if objective_terms:
        model.minimize(sum(objective_terms))

    # ---- Solve ----
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError("Could not find a feasible schedule. Check constraints and data.")

    # ---- Save results ----
    schedule = Schedule(target_month=month, status="preview")
    from datetime import datetime
    schedule.generated_at = datetime.utcnow()
    db.add(schedule)
    db.flush()

    assignments = []
    for e_id in emp_ids:
        for d in all_dates:
            if is_non_working_day(d):
                # Off day (weekend/holiday)
                a = ShiftAssignment(
                    schedule_id=schedule.id,
                    employee_id=e_id,
                    date=d,
                    job_type_id=None,
                    work_type="off",
                    headcount_value=0,
                )
                db.add(a)
                assignments.append({
                    "employee_id": e_id,
                    "employee_name": emp_names[e_id],
                    "date": d.isoformat(),
                    "job_type_id": None,
                    "work_type": "off",
                    "headcount_value": 0,
                })
                continue

            assigned_job = None
            for j in all_job_type_ids:
                if solver.value(x[e_id, d, j]) == 1:
                    assigned_job = j
                    break

            if assigned_job:
                # Determine work_type based on half-day off requests
                half_off_period = emp_half_off[e_id].get(d)
                if half_off_period == "am":
                    wt = "afternoon_half"  # AM off -> work PM
                    hc = 0.5
                elif half_off_period == "pm":
                    wt = "morning_half"  # PM off -> work AM
                    hc = 0.5
                else:
                    wt = "full"
                    hc = 1.0
                a = ShiftAssignment(
                    schedule_id=schedule.id,
                    employee_id=e_id,
                    date=d,
                    job_type_id=assigned_job,
                    work_type=wt,
                    headcount_value=hc,
                )
            else:
                a = ShiftAssignment(
                    schedule_id=schedule.id,
                    employee_id=e_id,
                    date=d,
                    job_type_id=None,
                    work_type="off",
                    headcount_value=0,
                )
            db.add(a)
            assignments.append({
                "employee_id": e_id,
                "employee_name": emp_names[e_id],
                "date": d.isoformat(),
                "job_type_id": assigned_job,
                "work_type": a.work_type,
                "headcount_value": a.headcount_value,
            })

    db.commit()

    # Check for violations (account for half-day headcount)
    for d in working_dates:
        if d not in daily_reqs:
            continue
        for j, req_count in daily_reqs[d].items():
            actual = sum(
                emp_hc_factor[e_id].get(d, 2) / 2
                for e_id in emp_ids
                if solver.value(x.get((e_id, d, j), model.new_constant(0))) == 1
            )
            if actual < req_count:
                violations.append(
                    f"{d.isoformat()} - job_type {j}: needed {req_count}, got {actual}"
                )

    return schedule.id, assignments, violations


def _apply_extra_constraint(
    model, x, work, constraint, emp_ids, emp_names,
    working_dates, all_job_type_ids, emp_job_types, db
):
    """Apply an extra constraint from NLP modification."""
    action = constraint.get("action")
    emp_name = constraint.get("employee_name")
    job_type_name = constraint.get("job_type")
    amount = constraint.get("amount")

    # Find employee id
    target_emp = None
    for e_id, name in emp_names.items():
        if name == emp_name:
            target_emp = e_id
            break
    if target_emp is None:
        return

    # Find job type id
    from database import JobType
    from sqlalchemy.orm import Session
    target_jt = None
    # We need to look up job type by name - use a simple approach
    for j in all_job_type_ids:
        jt = db.query(JobType).filter(JobType.id == j).first()
        if jt and jt.name == job_type_name:
            target_jt = j
            break

    if target_jt is None:
        return

    # Count of job_type assignments for employee
    jt_count = model.new_int_var(0, len(working_dates), f"nlp_jc_{target_emp}_{target_jt}")
    model.add(jt_count == sum(x[target_emp, d, target_jt] for d in working_dates))

    if action == "increase" and amount:
        # Current approximate count + amount
        model.add(jt_count >= amount)
    elif action == "decrease" and amount:
        model.add(jt_count <= max(0, amount))
    elif action == "set" and amount is not None:
        model.add(jt_count == amount)
