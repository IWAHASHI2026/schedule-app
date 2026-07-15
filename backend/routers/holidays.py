from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from database import get_db, CompanyHoliday
from models import HolidayOut, CompanyHolidayCreate
from datetime import date

router = APIRouter(prefix="/api/holidays", tags=["holidays"])

# Japanese holidays (2025-2027 covering typical usage)
JAPANESE_HOLIDAYS: dict[int, list[tuple[date, str]]] = {
    2025: [
        (date(2025, 1, 1), "元日"),
        (date(2025, 1, 13), "成人の日"),
        (date(2025, 2, 11), "建国記念の日"),
        (date(2025, 2, 23), "天皇誕生日"),
        (date(2025, 2, 24), "振替休日"),
        (date(2025, 3, 20), "春分の日"),
        (date(2025, 4, 29), "昭和の日"),
        (date(2025, 5, 3), "憲法記念日"),
        (date(2025, 5, 4), "みどりの日"),
        (date(2025, 5, 5), "こどもの日"),
        (date(2025, 5, 6), "振替休日"),
        (date(2025, 7, 21), "海の日"),
        (date(2025, 8, 11), "山の日"),
        (date(2025, 9, 15), "敬老の日"),
        (date(2025, 9, 23), "秋分の日"),
        (date(2025, 10, 13), "スポーツの日"),
        (date(2025, 11, 3), "文化の日"),
        (date(2025, 11, 23), "勤労感謝の日"),
        (date(2025, 11, 24), "振替休日"),
    ],
    2026: [
        (date(2026, 1, 1), "元日"),
        (date(2026, 1, 12), "成人の日"),
        (date(2026, 2, 11), "建国記念の日"),
        (date(2026, 2, 23), "天皇誕生日"),
        (date(2026, 3, 20), "春分の日"),
        (date(2026, 4, 29), "昭和の日"),
        (date(2026, 5, 3), "憲法記念日"),
        (date(2026, 5, 4), "みどりの日"),
        (date(2026, 5, 5), "こどもの日"),
        (date(2026, 5, 6), "振替休日"),
        (date(2026, 7, 20), "海の日"),
        (date(2026, 8, 11), "山の日"),
        (date(2026, 9, 21), "敬老の日"),
        (date(2026, 9, 22), "国民の休日"),
        (date(2026, 9, 23), "秋分の日"),
        (date(2026, 10, 12), "スポーツの日"),
        (date(2026, 11, 3), "文化の日"),
        (date(2026, 11, 23), "勤労感謝の日"),
    ],
    2027: [
        (date(2027, 1, 1), "元日"),
        (date(2027, 1, 11), "成人の日"),
        (date(2027, 2, 11), "建国記念の日"),
        (date(2027, 2, 23), "天皇誕生日"),
        (date(2027, 3, 21), "春分の日"),
        (date(2027, 3, 22), "振替休日"),
        (date(2027, 4, 29), "昭和の日"),
        (date(2027, 5, 3), "憲法記念日"),
        (date(2027, 5, 4), "みどりの日"),
        (date(2027, 5, 5), "こどもの日"),
        (date(2027, 7, 19), "海の日"),
        (date(2027, 8, 11), "山の日"),
        (date(2027, 9, 20), "敬老の日"),
        (date(2027, 9, 23), "秋分の日"),
        (date(2027, 10, 11), "スポーツの日"),
        (date(2027, 11, 3), "文化の日"),
        (date(2027, 11, 23), "勤労感謝の日"),
    ],
}


def get_holidays_for_year(year: int) -> list[tuple[date, str]]:
    return JAPANESE_HOLIDAYS.get(year, [])


def is_holiday(d: date) -> bool:
    holidays = get_holidays_for_year(d.year)
    return any(h[0] == d for h in holidays)


def get_company_holiday_dates(db: Session) -> frozenset[date]:
    """会社休業日の全日付をロードする（月・年で絞らない）。

    optimizer の SC-10 が前月の日付 (d-3) を参照するため、
    対象月に限定せず全件を返す必要がある。テーブルは高々数十行。
    """
    return frozenset(r.date for r in db.query(CompanyHoliday.date).all())


def is_non_working_day(d: date, company_holidays: frozenset[date] = frozenset()) -> bool:
    """Saturday, Sunday, Japanese holiday, or company holiday."""
    return d.weekday() >= 5 or is_holiday(d) or d in company_holidays


@router.get("", response_model=list[HolidayOut])
def list_holidays(year: int = 2026, db: Session = Depends(get_db)):
    result = [HolidayOut(date=h[0], name=h[1]) for h in get_holidays_for_year(year)]
    customs = (
        db.query(CompanyHoliday)
        .filter(
            CompanyHoliday.date >= date(year, 1, 1),
            CompanyHoliday.date <= date(year, 12, 31),
        )
        .all()
    )
    result += [HolidayOut(date=c.date, name=c.name, is_custom=True) for c in customs]
    result.sort(key=lambda h: h.date)
    return result


@router.post("", response_model=HolidayOut, status_code=201)
def add_company_holiday(body: CompanyHolidayCreate, db: Session = Depends(get_db)):
    d = body.date
    if d.weekday() >= 5:
        raise HTTPException(status_code=400, detail="土日はすでに休業日です")
    if is_holiday(d):
        raise HTTPException(status_code=400, detail="祝日はすでに休業日です")
    if db.query(CompanyHoliday).filter(CompanyHoliday.date == d).first():
        raise HTTPException(status_code=400, detail="この日付はすでに登録されています")
    rec = CompanyHoliday(date=d, name=body.name.strip() or "臨時休業")
    db.add(rec)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="この日付はすでに登録されています")
    return HolidayOut(date=rec.date, name=rec.name, is_custom=True)


@router.delete("/{holiday_date}", status_code=204)
def delete_company_holiday(holiday_date: date, db: Session = Depends(get_db)):
    rec = db.query(CompanyHoliday).filter(CompanyHoliday.date == holiday_date).first()
    if not rec:
        raise HTTPException(status_code=404, detail="この日付の休業日は登録されていません")
    db.delete(rec)
    db.commit()
