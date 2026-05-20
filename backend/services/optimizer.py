"""
Shift scheduling optimizer using Google OR-Tools CP-SAT solver.

Hard constraints（違反不可）:
  HC-01: Requested full-day off is always respected
         - Full day off (am+pm): employee cannot work
  HC-02: One job type per employee per day
  HC-03 上限: 日別必要人数を上限とし、超過配置を禁止
         - 不足分は「その他」の上限に加算（オーバーフロー）
         - 不足自体はソフト（ペナルティ）
  HC-04: Only assign job types the employee is qualified for
  HC-05: No work on weekends/holidays
  HC-06 上限/半日排除: 職人・サブ職人は各営業日に最大1名、半日勤務者は割当不可

Soft-hard constraints（可能な限り守るが、不可能なら違反として記録）:
  HC-01b: 半日休の日は残り半分を出勤（penalty 1,000,000）
  HC-06 下限: 職人・サブ職人は各営業日に1名配置（penalty 1,000,000）
  HC-04b: 日別必要人数未設定の職種への配置禁止（penalty 100,000）
  HC-07:  週出勤日数上限（penalty 500,000 per 超過日）
  HC-08:  連休明け1日目に調整休を入れない（penalty 1,000,000）
  → 違反時は violations リストに日本語メッセージとして追加

Soft constraints (objective function) — 4段階の優先順位:
  [Tier 1] フル勤務の希望日数:
    SC-01: Requested work days (full-time "max" weight 50, dependent "max" weight 8)
         - "max" = maximize work days (penalize non-work, soft)
         - Numeric value = hard upper limit on total work days
         - Full-time with no request = default to "max"
  [Tier 2] 仕事バランス:
    SC-04: Job type balance per employee (weight 10, 全社員で統一)
    SC-08: Cross-employee fairness per job type across all qualified employees (full-time weight 5, dependent weight 1)
  [Tier 3] 扶養内の希望日数:
    SC-09: Dependent staff minimum work days target (weight 8, default 10 days)
  [Tier 4] 扶養内の cross-employee fairness: (SC-08 の dependent weights のみ)
  Other:
    SC-05: Prefer higher-priority job types (weight 2)
    SC-06: Prefer full-time employees over dependent (weight 3)
    SC-07: Avoid same job type on consecutive working days (weight 5)
    SC-10: 2日以上連休の翌々日への出勤誘導 (weight 100, 極力出勤)
           - 連休明け1日目は HC-08 (hard-soft) で対応
    SC-11: 資格職種のゼロ日数防止 (weight 500)
           - 資格を持ち、その月の daily_requirements に1日以上設定がある職種を
             0日にしないよう強くペナルティ
    Shortage penalty: Priority-weighted (higher priority = higher penalty)
"""

import logging
from ortools.sat.python import cp_model
from sqlalchemy.orm import Session
from database import (
    Employee, EmployeeJobType, ShiftRequest, RequestDetail,
    DailyRequirement, Schedule, ShiftAssignment,
)
from routers.holidays import is_non_working_day
from datetime import date, timedelta

logger = logging.getLogger(__name__)
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
    emp_type = {e.id: e.employment_type for e in employees}

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

    # Job type sort_order mapping (for priority constraint)
    from database import JobType as JT
    jt_sort_order: dict[int, int] = {
        jt.id: jt.sort_order for jt in db.query(JT).all()
    }

    # Requested days off per employee (with period info)
    emp_off_periods: dict[int, dict[date, set[str]]] = {}  # e_id -> date -> {"am","pm"}
    emp_requested_work: dict[int, str | None] = {}  # "1"-"23" or "max" or None
    emp_weekly_limit: dict[int, int | None] = {}  # e_id -> weekly limit or None

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
            emp_weekly_limit[e_id] = req.weekly_work_day_limit
        else:
            emp_off_periods[e_id] = {}
            emp_requested_work[e_id] = None
            emp_weekly_limit[e_id] = None

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

    # 違反追跡用のslack変数（常に強制生成できるようソフト化されたハード制約）
    hc01b_violations: list = []  # [(slack_var, e_id, d)]
    hc06_violations: list = []   # [(slack_var, d, j)]
    hc04b_violations: list = []  # [(slack_var, e_id, d, j)]
    hc07_violations: list = []   # [(over_var, e_id, week_key, wlimit, week_dates)]
    hc08_violations: list = []   # [(slack_var, e_id, d)]  - 連休明け1日目の調整休禁止

    # HC-01b (SOFT): Half-day off -> should work the remaining half
    # 強制生成のためソフト化。違反時は大ペナルティ。
    for e_id in emp_ids:
        for d in working_dates:
            if d in emp_half_off[e_id]:
                v = model.new_bool_var(f"viol_hc01b_{e_id}_{d.isoformat()}")
                # work==1 OR v==1
                model.add(work[e_id, d] + v >= 1)
                hc01b_violations.append((v, e_id, d))

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

    # HC-06: 職人・サブ職人は各営業日に1名配置
    # - 上限1: ハード（超過禁止）
    # - 下限1: ソフト（0名時は違反として記録）
    # - 半日勤務者の配置禁止: ハード（業務ルール）
    from database import JobType
    hard_one_jt_ids = set()
    # 「その他」のjob_type_idを取得（オーバーフロー先）
    sono_ta_jt = db.query(JobType).filter(JobType.name == "その他").first()
    sono_ta_jt_id = sono_ta_jt.id if sono_ta_jt else None
    for jt in db.query(JobType).filter(JobType.name.in_(["職人", "サブ職人"])).all():
        hard_one_jt_ids.add(jt.id)
    for d in working_dates:
        for j in hard_one_jt_ids:
            if j in all_job_type_ids:
                # 半日勤務者はこの職種に割り当てない（ハード維持）
                for e_id in emp_ids:
                    if d in emp_half_off[e_id] and j in emp_job_types.get(e_id, []):
                        model.add(x[e_id, d, j] == 0)
                total = sum(
                    x[e_id, d, j] for e_id in emp_ids if j in emp_job_types.get(e_id, [])
                )
                # 上限: ハード
                model.add(total <= 1)
                # 下限: ソフト（0のときはv=1）
                v = model.new_bool_var(f"viol_hc06_{d.isoformat()}_{j}")
                model.add(total + v >= 1)
                hc06_violations.append((v, d, j))

    # HC-04b (SOFT): 必要人数未設定職種への配置
    # 強制生成のためソフト化。通常は配置しない（ペナルティあり）。
    for d in working_dates:
        reqs_for_day = daily_reqs.get(d, {})
        for j in all_job_type_ids:
            if j in hard_one_jt_ids:
                continue  # 職人・サブ職人はHC-06で管理
            if j not in reqs_for_day:
                for e_id in emp_ids:
                    if j in emp_job_types.get(e_id, []):
                        v = model.new_bool_var(f"viol_hc04b_{e_id}_{d.isoformat()}_{j}")
                        # x==1 の場合は v==1 にする
                        model.add(x[e_id, d, j] <= v)
                        hc04b_violations.append((v, e_id, d, j))

    # HC-08 (SOFT): 連休明け1日目に調整休を入れない（出荷集中日の絶対出勤）
    # 強制生成のためソフト化。月間上限が逼迫等で物理的に不可能な場合のみ違反として記録。
    # HC-01(希休) と HC-01b(半日休) は対象外（個別ルールが優先）。
    for d in working_dates:
        prev_d = d - timedelta(days=1)
        if not is_non_working_day(prev_d):
            continue  # 連休明け1日目ではない
        for e_id in emp_ids:
            if d in emp_full_off[e_id]:
                continue  # HC-01 (希休) を優先
            if d in emp_half_off[e_id]:
                continue  # HC-01b が半日勤務を担保
            v = model.new_bool_var(f"viol_hc08_{e_id}_{d.isoformat()}")
            # work==1 OR v==1
            model.add(work[e_id, d] + v >= 1)
            hc08_violations.append((v, e_id, d))

    # HC-07 (SOFT): Weekly work day limit per employee
    # 強制生成のためソフト化。超過分をペナルティ。
    from collections import defaultdict
    weeks: dict[tuple[int, int], list[date]] = defaultdict(list)
    for d in working_dates:
        iso_year, iso_week, _ = d.isocalendar()
        weeks[(iso_year, iso_week)].append(d)

    for e_id in emp_ids:
        wlimit = emp_weekly_limit.get(e_id)
        if wlimit is not None:
            for week_key, week_dates in weeks.items():
                over = model.new_int_var(
                    0, len(week_dates), f"over_hc07_{e_id}_{week_key[0]}_{week_key[1]}"
                )
                model.add(sum(work[e_id, d] for d in week_dates) - wlimit <= over)
                hc07_violations.append((over, e_id, week_key, wlimit, week_dates))

    # HC-03: Daily requirements as upper limits with overflow to その他
    # - 必要人数を上限とし、超過配置を禁止（ハード制約）
    # - 不足分はペナルティ付きソフト制約で追跡
    # - 他職種の不足分は「その他」の上限に加算（オーバーフロー）
    # Using integer scaling: multiply by 2 for 0.5 support
    # Half-day workers contribute 1 unit (0.5), full-day workers contribute 2 units (1.0)
    violations = []
    shortage_vars = []  # Track shortages for objective penalty: (var, job_type_id)
    for d in working_dates:
        if d not in daily_reqs:
            continue
        day_overflow = []  # 他職種の不足分（その他にオーバーフロー）
        for j, req_count in daily_reqs[d].items():
            if j in hard_one_jt_ids:
                continue  # Already enforced as hard constraint above
            if j == sono_ta_jt_id:
                continue  # その他はオーバーフロー集計後に処理
            scaled_req = int(req_count * 2)
            supply = sum(
                x[e_id, d, j] * emp_hc_factor[e_id].get(d, 2)
                for e_id in emp_ids
                if j in emp_job_types.get(e_id, [])
            )
            # Upper limit: 必要人数を超えて配置しない
            model.add(supply <= scaled_req)
            # Shortage tracking: 不足分をトラッキング
            shortage = model.new_int_var(0, scaled_req, f"shortage_{d}_{j}")
            model.add(shortage >= scaled_req - supply)
            shortage_vars.append((shortage, j))
            day_overflow.append(shortage)

        # その他: 上限 = 基本要件 + 他職種の不足分（オーバーフロー）
        if sono_ta_jt_id and sono_ta_jt_id in all_job_type_ids:
            sono_ta_req = daily_reqs[d].get(sono_ta_jt_id, 0)
            scaled_sono_ta_req = int(sono_ta_req * 2)
            sono_ta_supply = sum(
                x[e_id, d, sono_ta_jt_id] * emp_hc_factor[e_id].get(d, 2)
                for e_id in emp_ids
                if sono_ta_jt_id in emp_job_types.get(e_id, [])
            )
            # Upper limit with overflow
            if day_overflow:
                model.add(sono_ta_supply <= scaled_sono_ta_req + sum(day_overflow))
                # Effective cap for shortage calculation
                effective_cap = model.new_int_var(
                    0, scaled_sono_ta_req + len(emp_ids) * 2, f"sonota_cap_{d}"
                )
                model.add(effective_cap == scaled_sono_ta_req + sum(day_overflow))
            else:
                model.add(sono_ta_supply <= scaled_sono_ta_req)
                effective_cap = scaled_sono_ta_req
            # Shortage for その他
            sono_ta_shortage = model.new_int_var(
                0, scaled_sono_ta_req + len(emp_ids) * 2, f"shortage_{d}_{sono_ta_jt_id}"
            )
            model.add(sono_ta_shortage >= effective_cap - sono_ta_supply)
            shortage_vars.append((sono_ta_shortage, sono_ta_jt_id))

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

    # SC-01: Requested work days (Tier 1: full-time weight 50, Tier 3: dependent weight 8)
    # - "max": soft constraint to maximize work days
    # - numeric: hard upper limit constraint
    # - full-time with no request: default to "max"
    for e_id in emp_ids:
        rw = emp_requested_work.get(e_id)
        is_fulltime = emp_type[e_id] == "full_time"
        work_day_weight = 50 if is_fulltime else 8  # Tier 1 vs Tier 3
        if rw == "max":
            not_work_count = model.new_int_var(0, scaled_total, f"not_work_{e_id}")
            model.add(not_work_count == scaled_total - emp_total_work[e_id])
            objective_terms.append(not_work_count * work_day_weight)
        elif rw is not None:
            # Hard upper limit (scaled by 2)
            target = int(rw) * 2
            model.add(emp_total_work[e_id] <= target)
        elif is_fulltime:
            # フル勤務でリクエストなし → デフォルトでmax扱い
            not_work_count = model.new_int_var(0, scaled_total, f"not_work_{e_id}")
            model.add(not_work_count == scaled_total - emp_total_work[e_id])
            objective_terms.append(not_work_count * work_day_weight)

    # SC-09: 扶養内スタッフの最低出勤日数ターゲット（Tier 3, weight 8, デフォルト10日）
    DEPENDENT_DEFAULT_TARGET = 10
    for e_id in emp_ids:
        if emp_type[e_id] != "dependent":
            continue
        rw = emp_requested_work.get(e_id)
        if rw == "max":
            continue  # 既存のSC-01で最大化される
        # 目標日数: 数値指定があればその値、なければデフォルト10日
        target_days = int(rw) if rw is not None else DEPENDENT_DEFAULT_TARGET
        scaled_target = target_days * 2
        # 目標との不足分をペナルティ（Tier 3: weight 8）
        shortfall = model.new_int_var(0, scaled_total, f"dep_short_{e_id}")
        model.add(shortfall >= scaled_target - emp_total_work[e_id])
        objective_terms.append(shortfall * 8)

    # SC-04: Job type balance per employee — pairwise
    # 全社員で weight 10 (雇用形態問わず統一)
    emp_job_counts: dict[int, dict[int, cp_model.IntVar]] = {}
    for e_id in emp_ids:
        allowed = emp_job_types.get(e_id, [])
        if not allowed:
            continue
        job_counts: dict[int, cp_model.IntVar] = {}
        for j in allowed:
            jc = model.new_int_var(0, total_working_dates, f"jc_{e_id}_{j}")
            model.add(jc == sum(x[e_id, d, j] for d in working_dates))
            job_counts[j] = jc
        emp_job_counts[e_id] = job_counts
        if len(allowed) <= 1:
            continue
        balance_weight = 10  # 全社員で同一 (旧: dep は weight 2)
        for i in range(len(allowed)):
            for k in range(i + 1, len(allowed)):
                j1, j2 = allowed[i], allowed[k]
                diff = model.new_int_var(0, total_working_dates, f"jcdiff_{e_id}_{j1}_{j2}")
                model.add(diff >= job_counts[j1] - job_counts[j2])
                model.add(diff >= job_counts[j2] - job_counts[j1])
                objective_terms.append(diff * balance_weight)

    # SC-08: Cross-employee job type fairness — per job type across all qualified employees
    # Tier 2: full-time pairs weight 5, Tier 4: dependent pairs weight 1
    # 各職種について、その職種を担当可能な全スタッフ間で公平性制約を作成
    # （旧実装は完全一致の資格グループのみ対象だったため、1つでも資格が異なる
    #   スタッフが孤立し、特定職種に偏る問題があった）
    from itertools import combinations
    for j in all_job_type_ids:
        qualified = [e_id for e_id in emp_ids
                     if j in emp_job_types.get(e_id, [])
                     and j in emp_job_counts.get(e_id, {})]
        if len(qualified) <= 1:
            continue
        for e1, e2 in combinations(qualified, 2):
            # 両者がフル勤務ならTier 2、それ以外はTier 4
            both_fulltime = emp_type[e1] == "full_time" and emp_type[e2] == "full_time"
            fairness_weight = 5 if both_fulltime else 1
            diff = model.new_int_var(0, total_working_dates, f"sc08_{e1}_{e2}_{j}")
            model.add(diff >= emp_job_counts[e1][j] - emp_job_counts[e2][j])
            model.add(diff >= emp_job_counts[e2][j] - emp_job_counts[e1][j])
            objective_terms.append(diff * fairness_weight)

    # SC-11: 資格職種のゼロ日数防止 (weight 500)
    # その月の daily_requirements に1日でも設定がある職種について、
    # 資格を持つスタッフがその職種で 0 日にならないよう強くペナルティを付与。
    # SC-04 (バランス) は「少なすぎ」を罰するが、絶対値0は別途防ぐ必要があるため独立構成。
    SC11_WEIGHT = 500
    jobs_with_demand: set[int] = set()
    for d in working_dates:
        for j in daily_reqs.get(d, {}):
            jobs_with_demand.add(j)
    for e_id in emp_ids:
        for j in emp_job_types.get(e_id, []):
            if j not in jobs_with_demand:
                continue  # その月に需要のない職種はスキップ (HC-04b 領域)
            if j not in emp_job_counts.get(e_id, {}):
                continue
            # zero_flag = 1 iff count == 0 (bigM 線形化)
            zero_flag = model.new_bool_var(f"sc11_zero_{e_id}_{j}")
            model.add(emp_job_counts[e_id][j] + total_working_dates * zero_flag >= 1)
            objective_terms.append(zero_flag * SC11_WEIGHT)

    # SC-05: Priority cost - prefer lower sort_order (1=職人, 2=サブ, 3=lkデータ, 4=uv/cpデータ, 5=手紙, 6=その他)
    priority_weight = 2
    for e_id in emp_ids:
        for d in working_dates:
            for j in all_job_type_ids:
                objective_terms.append(x[e_id, d, j] * jt_sort_order.get(j, j) * priority_weight)

    # SC-06: Prefer full-time employees over dependent (weight 3)
    # 優先順位の差はウェイト階層(Tier 1-4)で主に処理済み
    for e_id in emp_ids:
        if emp_type[e_id] == "dependent":
            for d in working_dates:
                objective_terms.append(work[e_id, d] * 3)

    # SC-07: Avoid same job type on consecutive working days (weight 5)
    for e_id in emp_ids:
        allowed = emp_job_types.get(e_id, [])
        if len(allowed) <= 1:
            continue  # Only one job type available, cannot vary
        for i in range(len(working_dates) - 1):
            d1 = working_dates[i]
            d2 = working_dates[i + 1]
            for j in allowed:
                consec = model.new_bool_var(f"consec_{e_id}_{d1}_{j}")
                model.add(consec >= x[e_id, d1, j] + x[e_id, d2, j] - 1)
                objective_terms.append(consec * 5)

    # SC-10: 2日以上連休の翌々日への出勤誘導 (weight 100, 極力出勤)
    # 連休明け1日目 (Rule 1) は HC-08 (hard-soft, 1M penalty) で対応するため、
    # ここは Rule 2 (例: 通常週の火曜、3連休後の水曜) のみを担当する強めのソフト誘導。
    # weight=100 で SC-01(50)/SC-04(10) を明確に上回り、shortage penalty(100)と同等。
    SC10_WEIGHT = 100
    for d in working_dates:
        prev_d = d - timedelta(days=1)
        if is_non_working_day(prev_d):
            continue  # Rule 1 days are handled by HC-08
        # Rule 2: prev_d が営業日 かつ d-2, d-3 が両方非営業日 → 直前の連休 >= 2日
        if not (is_non_working_day(d - timedelta(days=2))
                and is_non_working_day(d - timedelta(days=3))):
            continue
        for e_id in emp_ids:
            # 出勤しない (work=0) 場合にペナルティ → 出勤側へ誘導
            objective_terms.append((1 - work[e_id, d]) * SC10_WEIGHT)

    # Penalty for requirement shortages — priority-weighted
    # 優先順位の高い職種ほど不足ペナルティを大きくし、
    # スタッフ不足時は優先順位の低い仕事から人数を減らす
    max_sort = max(jt_sort_order.values()) if jt_sort_order else 6
    for sv, j in shortage_vars:
        priority_factor = max_sort + 1 - jt_sort_order.get(j, max_sort)
        objective_terms.append(sv * 100 * priority_factor)

    # 強制生成のためソフト化したハード制約の違反には大ペナルティを付与
    # （他のソフト制約ペナルティ ~700/unit より十分大きい値で、
    #   可能な限り満たされるが不可能時は緩和される）
    HC01B_PENALTY = 1_000_000
    HC06_PENALTY = 1_000_000
    HC04B_PENALTY = 100_000
    HC07_PENALTY = 500_000
    HC08_PENALTY = 1_000_000  # 連休明け1日目の調整休禁止 - 「絶対」を表現
    for v, _, _ in hc01b_violations:
        objective_terms.append(v * HC01B_PENALTY)
    for v, _, _ in hc06_violations:
        objective_terms.append(v * HC06_PENALTY)
    for v, _, _, _ in hc04b_violations:
        objective_terms.append(v * HC04B_PENALTY)
    for over, _, _, _, _ in hc07_violations:
        objective_terms.append(over * HC07_PENALTY)
    for v, _, _ in hc08_violations:
        objective_terms.append(v * HC08_PENALTY)

    if objective_terms:
        model.minimize(sum(objective_terms))

    # ---- Solve ----
    # 並列探索 + 十分な時間で、バランス制約(SC-04/08/11)まで最適化されるようにする。
    # モデル肥大化(HC-08/SC-10/SC-11追加)に伴い、旧設定(30秒・単一ワーカー)では
    # 重みの小さいバランス目的が最適化されきらず偏りが残っていた。
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    solver.parameters.num_search_workers = 8  # 並列ポートフォリオ探索
    status = solver.solve(model)
    logger.info(
        "schedule solve: status=%s objective=%s bound=%s wall=%.1fs",
        solver.status_name(status),
        solver.objective_value if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        solver.best_objective_bound if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        solver.wall_time,
    )

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        reasons = _diagnose_infeasibility(
            emp_ids, emp_names, emp_job_types, emp_full_off, emp_half_off,
            working_dates, hard_one_jt_ids, all_job_type_ids, db,
            daily_reqs, emp_weekly_limit,
        )
        if reasons:
            msg = "スケジュールを生成できませんでした。以下の問題が見つかりました:\n" + "\n".join(reasons)
        else:
            msg = "スケジュールを生成できませんでした。制約条件とデータを確認してください。"
        raise ValueError(msg)

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
    dow_names = ["月", "火", "水", "木", "金", "土", "日"]
    jt_name_map = {jt.id: jt.name for jt in db.query(JobType).all()}
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
                jt_name = jt_name_map.get(j, f"職種{j}")
                shortage = req_count - actual
                dow = dow_names[d.weekday()]
                actual_str = int(actual) if actual == int(actual) else actual
                req_str = int(req_count) if req_count == int(req_count) else req_count
                violations.append(
                    f"{d.month}月{d.day}日（{dow}）: {jt_name}が{shortage:g}名不足（必要{req_str}名、配置{actual_str}名）"
                )

    # ソフト化したハード制約の違反を抽出
    for v, e_id, d in hc01b_violations:
        if solver.value(v) == 1:
            dow = dow_names[d.weekday()]
            violations.append(
                f"{d.month}月{d.day}日（{dow}）: "
                f"{emp_names[e_id]}の半日休の残り半分を出勤にできませんでした（HC-01b）"
            )
    for v, e_id, d in hc08_violations:
        if solver.value(v) == 1:
            dow = dow_names[d.weekday()]
            violations.append(
                f"{d.month}月{d.day}日（{dow}）: "
                f"{emp_names[e_id]}の調整休を回避できませんでした（HC-08: 連休明け）"
            )
    for v, d, j in hc06_violations:
        if solver.value(v) == 1:
            dow = dow_names[d.weekday()]
            jt_name = jt_name_map.get(j, f"職種{j}")
            violations.append(
                f"{d.month}月{d.day}日（{dow}）: "
                f"{jt_name}に1名配置できませんでした（HC-06）"
            )
    hc04b_by_emp_day: dict[tuple, list[str]] = {}
    for v, e_id, d, j in hc04b_violations:
        if solver.value(v) == 1:
            jt_name = jt_name_map.get(j, f"職種{j}")
            hc04b_by_emp_day.setdefault((e_id, d), []).append(jt_name)
    for (e_id, d), jt_names in hc04b_by_emp_day.items():
        dow = dow_names[d.weekday()]
        violations.append(
            f"{d.month}月{d.day}日（{dow}）: "
            f"{emp_names[e_id]}を必要人数未設定の{'・'.join(jt_names)}に配置しました（HC-04b）"
        )
    for over, e_id, week_key, wlimit, week_dates in hc07_violations:
        overflow = solver.value(over)
        if overflow > 0:
            first = week_dates[0]
            last = week_dates[-1]
            violations.append(
                f"{first.month}月{first.day}日〜{last.month}月{last.day}日: "
                f"{emp_names[e_id]}の週上限{wlimit}日を{overflow}日超過しました（HC-07）"
            )

    return schedule.id, assignments, violations


def _diagnose_infeasibility(
    emp_ids, emp_names, emp_job_types, emp_full_off, emp_half_off,
    working_dates, hard_one_jt_ids, all_job_type_ids, db,
    daily_reqs, emp_weekly_limit,
) -> list[str]:
    """ソルバー失敗時の原因を診断し、日本語メッセージのリストを返す。"""
    from database import JobType
    from collections import defaultdict
    reasons = []
    dow_names = ["月", "火", "水", "木", "金", "土", "日"]
    jt_name_map = {jt.id: jt.name for jt in db.query(JobType).all()}

    # チェック1: HC-06 — 職人/サブ職人が配置不可能な日
    for j in hard_one_jt_ids:
        jt_name = jt_name_map.get(j, f"職種{j}")
        for d in working_dates:
            available = []
            unavailable = []
            for e_id in emp_ids:
                if j not in emp_job_types.get(e_id, []):
                    continue
                if d in emp_full_off[e_id]:
                    unavailable.append(emp_names[e_id] + "（希望休）")
                elif d in emp_half_off[e_id]:
                    unavailable.append(emp_names[e_id] + "（半日休）")
                else:
                    available.append(emp_names[e_id])
            if len(available) == 0:
                dow = dow_names[d.weekday()]
                reason = (
                    f"{d.month}月{d.day}日（{dow}）: "
                    f"{jt_name}の資格者が全員休みのため配置できません"
                )
                if unavailable:
                    reason += f"（{', '.join(unavailable)}）"
                reasons.append(reason)

    # チェック2: HC-06 同時配置 — 職人+サブ職人の候補が不足
    if len(hard_one_jt_ids) >= 2:
        for d in working_dates:
            available_per_jt: dict[int, set[int]] = {}
            for j in hard_one_jt_ids:
                avail: set[int] = set()
                for e_id in emp_ids:
                    if j not in emp_job_types.get(e_id, []):
                        continue
                    if d in emp_full_off[e_id] or d in emp_half_off[e_id]:
                        continue
                    avail.add(e_id)
                available_per_jt[j] = avail
            # 全職種に1人ずつ必要 → ユニーク人数が足りるか
            all_available: set[int] = set()
            for avail in available_per_jt.values():
                all_available |= avail
            if len(all_available) < len(hard_one_jt_ids):
                dow = dow_names[d.weekday()]
                jt_names = [jt_name_map.get(j, "") for j in hard_one_jt_ids]
                reasons.append(
                    f"{d.month}月{d.day}日（{dow}）: "
                    f"{'・'.join(jt_names)}を同時に配置できるスタッフが不足しています"
                    f"（必要{len(hard_one_jt_ids)}名、利用可能{len(all_available)}名）"
                )

    # チェック3: HC-04 — 資格者不在の職種
    for j in all_job_type_ids:
        qualified = [e_id for e_id in emp_ids if j in emp_job_types.get(e_id, [])]
        if len(qualified) == 0:
            jt_name = jt_name_map.get(j, f"職種{j}")
            reasons.append(f"「{jt_name}」に資格のあるスタッフが登録されていません")

    # チェック4: HC-01b × HC-06 — 半日休なのに担当可能職種が職人/サブ職人のみ
    for e_id in emp_ids:
        allowed = set(emp_job_types.get(e_id, []))
        non_hard = allowed - hard_one_jt_ids
        if non_hard:
            continue  # 他の職種でカバー可能
        if not (allowed & hard_one_jt_ids):
            continue  # そもそも職人/サブ職人も担当不可（チェック3で扱う）
        for d, _ in emp_half_off[e_id].items():
            if d not in working_dates:
                continue
            dow = dow_names[d.weekday()]
            reasons.append(
                f"{d.month}月{d.day}日（{dow}）: "
                f"{emp_names[e_id]}は半日休ですが、担当可能な職種が"
                f"職人・サブ職人のみのため配置できません（HC-01b × HC-06）"
            )

    # チェック5: HC-01b × HC-04b — 半日休なのにその日に必要人数設定のある担当可能職種が無い
    for e_id in emp_ids:
        allowed = set(emp_job_types.get(e_id, [])) - hard_one_jt_ids
        if not allowed:
            continue  # チェック4で扱う
        for d, _ in emp_half_off[e_id].items():
            if d not in working_dates:
                continue
            reqs_for_day = daily_reqs.get(d, {})
            assignable = allowed & set(reqs_for_day.keys())
            if not assignable:
                dow = dow_names[d.weekday()]
                allowed_names = [jt_name_map.get(j, f"職種{j}") for j in sorted(allowed)]
                reasons.append(
                    f"{d.month}月{d.day}日（{dow}）: "
                    f"{emp_names[e_id]}は半日休ですが、その日の必要人数設定に"
                    f"担当可能な職種（{', '.join(allowed_names)}）が含まれていないため配置できません"
                    f"（HC-01b × HC-04b）"
                )

    # チェック6: HC-01b × HC-07 — 週上限より半日休の強制出勤日数が多い
    weeks: dict[tuple[int, int], list] = defaultdict(list)
    for d in working_dates:
        iso_year, iso_week, _ = d.isocalendar()
        weeks[(iso_year, iso_week)].append(d)
    for e_id in emp_ids:
        wlimit = emp_weekly_limit.get(e_id)
        if wlimit is None:
            continue
        for week_key, week_dates in weeks.items():
            forced = [d for d in week_dates if d in emp_half_off[e_id]]
            if len(forced) > wlimit:
                range_str = f"{forced[0].month}月{forced[0].day}日〜{forced[-1].month}月{forced[-1].day}日"
                reasons.append(
                    f"{range_str}: {emp_names[e_id]}は週上限{wlimit}日に対して"
                    f"半日休による出勤強制が{len(forced)}日あります（HC-01b × HC-07）"
                )

    # チェック7: 必要人数に対して利用可能資格者が不足している日・職種
    for d in working_dates:
        reqs_for_day = daily_reqs.get(d, {})
        for j, req_count in reqs_for_day.items():
            if j in hard_one_jt_ids:
                continue  # HC-06 側で扱う
            if req_count <= 0:
                continue
            avail_full = 0
            avail_half = 0
            for e_id in emp_ids:
                if j not in emp_job_types.get(e_id, []):
                    continue
                if d in emp_full_off[e_id]:
                    continue
                if d in emp_half_off[e_id]:
                    avail_half += 1
                else:
                    avail_full += 1
            # 半日勤務は 0.5 人分として計算
            capacity = avail_full + avail_half * 0.5
            if capacity < req_count:
                dow = dow_names[d.weekday()]
                jt_name = jt_name_map.get(j, f"職種{j}")
                req_str = int(req_count) if req_count == int(req_count) else req_count
                cap_str = int(capacity) if capacity == int(capacity) else capacity
                reasons.append(
                    f"{d.month}月{d.day}日（{dow}）: "
                    f"{jt_name}は必要{req_str}名ですが、利用可能な資格者が"
                    f"{cap_str}名分しかいません（フル{avail_full}名＋半日{avail_half}名）"
                )

    return reasons


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
