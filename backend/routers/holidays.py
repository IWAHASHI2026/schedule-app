from fastapi import APIRouter
from models import HolidayOut
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


def is_non_working_day(d: date) -> bool:
    """Saturday, Sunday, or Japanese holiday."""
    return d.weekday() >= 5 or is_holiday(d)


@router.get("", response_model=list[HolidayOut])
def list_holidays(year: int = 2026):
    holidays = get_holidays_for_year(year)
    return [HolidayOut(date=h[0], name=h[1]) for h in holidays]
