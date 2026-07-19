"""カス取りスタッフの月次出欠 API。

カス取りスタッフはシフト自動生成（CP-SAT）の対象外で、
デフォルト曜日パターン + 日単位の上書きで出欠を管理する。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from datetime import date
import calendar

from database import get_db, KasutoriStaff, KasutoriAttendance
from models import KasutoriStaffMonthOut, KasutoriAttendanceUpdate
from routers.holidays import is_non_working_day, get_company_holiday_dates

router = APIRouter(prefix="/api/kasutori", tags=["kasutori"])


def resolve_kasutori_month(db: Session, month: str) -> list[dict]:
    """月次の出欠を解決して返す。優先順位: 非営業日 > 上書き > デフォルト曜日。

    weekday 規約: Python date.weekday() Mon=0..Sun=6（default_weekdays と同一規約）。
    フロントには解決済みの 日付→状態 マップのみ渡すため JS の getDay() 規約(Sun=0)とは無関係。
    """
    try:
        year, mon = map(int, month.split("-"))
        days_in_month = calendar.monthrange(year, mon)[1]
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="月の形式が不正です (YYYY-MM)")

    dates = [date(year, mon, d) for d in range(1, days_in_month + 1)]
    company_holidays = get_company_holiday_dates(db)
    staff_list = db.query(KasutoriStaff).order_by(KasutoriStaff.sort_order).all()
    overrides = (
        db.query(KasutoriAttendance)
        .filter(KasutoriAttendance.date >= dates[0], KasutoriAttendance.date <= dates[-1])
        .all()
    )
    ov_map = {(o.staff_id, o.date): o.is_working for o in overrides}

    result = []
    for s in staff_list:
        # 不正なトークン（非数値・範囲外）は無視して壊れないようにする
        default_wd = frozenset(
            int(x) for x in s.default_weekdays.split(",")
            if x.strip().isdigit() and 0 <= int(x) <= 6
        )
        days: dict[str, str] = {}
        total = 0
        for d in dates:
            if is_non_working_day(d, company_holidays):
                status = "off"  # 土日祝・会社休業日は常に休み（上書きより優先）
            elif (s.id, d) in ov_map:
                status = "work" if ov_map[(s.id, d)] == 1 else "off"
            else:
                status = "work" if d.weekday() in default_wd else "off"
            days[d.isoformat()] = status
            if status == "work":
                total += 1
        result.append({
            "staff_id": s.id,
            "name": s.name,
            "sort_order": s.sort_order,
            "days": days,
            "total": total,
        })
    return result


@router.get("", response_model=list[KasutoriStaffMonthOut])
def get_kasutori_month(month: str, db: Session = Depends(get_db)):
    return resolve_kasutori_month(db, month)


def _upsert_attendance_items(db: Session, items: dict[tuple[int, date], int]) -> None:
    for (staff_id, d), val in items.items():
        existing = (
            db.query(KasutoriAttendance)
            .filter(
                KasutoriAttendance.staff_id == staff_id,
                KasutoriAttendance.date == d,
            )
            .first()
        )
        if existing:
            existing.is_working = val
        else:
            db.add(KasutoriAttendance(staff_id=staff_id, date=d, is_working=val))


@router.put("/attendance")
def update_kasutori_attendance(body: KasutoriAttendanceUpdate, db: Session = Depends(get_db)):
    valid_ids = {s.id for s in db.query(KasutoriStaff).all()}
    for item in body.items:
        if item.staff_id not in valid_ids:
            raise HTTPException(status_code=404, detail=f"カス取りスタッフが見つかりません: id={item.staff_id}")

    # 同一 (staff_id, date) の重複は後勝ちで統合（autoflush=False のため
    # ループ内の .first() は同一ペイロード内の未 flush 行を見ないので、事前に統合しておく）
    deduped = {(item.staff_id, item.date): (1 if item.is_working else 0) for item in body.items}

    _upsert_attendance_items(db, deduped)
    try:
        db.commit()
    except IntegrityError:
        # 同時保存で同じ (staff_id, date) が先に挿入された場合は update としてやり直す
        db.rollback()
        _upsert_attendance_items(db, deduped)
        db.commit()
    return {"status": "ok", "saved": len(deduped)}
