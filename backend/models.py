from pydantic import BaseModel
from typing import Optional
from datetime import date


# ---- Employee ----

class EmployeeCreate(BaseModel):
    name: str
    employment_type: str = "full_time"  # "full_time" or "dependent"

class EmployeeUpdate(BaseModel):
    name: str
    employment_type: str = "full_time"

class JobTypeOut(BaseModel):
    id: int
    name: str
    color: Optional[str] = None

class EmployeeOut(BaseModel):
    id: int
    name: str
    employment_type: str = "full_time"
    job_types: list[JobTypeOut] = []

class EmployeeJobTypesUpdate(BaseModel):
    job_type_ids: list[int]


# ---- Shift Requests ----

class DayOffItem(BaseModel):
    date: date
    period: str = "all_day"  # "am", "pm", or "all_day"

class ShiftRequestCreate(BaseModel):
    employee_id: int
    target_month: str
    requested_work_days: Optional[str] = None  # "1"-"23" or "max"
    note: Optional[str] = None
    days_off: list[DayOffItem] = []

class RequestDetailOut(BaseModel):
    id: int
    date: date
    period: str = "all_day"

class ShiftRequestOut(BaseModel):
    id: int
    employee_id: int
    employee_name: str = ""
    target_month: str
    requested_work_days: Optional[str] = None
    note: Optional[str] = None
    details: list[RequestDetailOut] = []

class RequestStatusOut(BaseModel):
    employee_id: int
    employee_name: str
    has_request: bool


# ---- Daily Requirements ----

class DailyRequirementItem(BaseModel):
    date: date
    job_type_id: int
    required_count: float

class DailyRequirementsCreate(BaseModel):
    items: list[DailyRequirementItem]

class DailyRequirementOut(BaseModel):
    id: int
    date: date
    job_type_id: int
    job_type_name: str = ""
    required_count: float

class TemplateItem(BaseModel):
    job_type_id: int
    required_count: float

class RequirementsTemplate(BaseModel):
    month: str
    weekday_requirements: dict[int, list[TemplateItem]]  # 0=Mon..4=Fri


# ---- Schedule ----

class ScheduleOut(BaseModel):
    id: int
    target_month: str
    status: str
    generated_at: Optional[str] = None
    confirmed_at: Optional[str] = None

class ShiftAssignmentOut(BaseModel):
    id: int
    schedule_id: int
    employee_id: int
    employee_name: str = ""
    date: date
    job_type_id: Optional[int] = None
    job_type_name: Optional[str] = None
    job_type_color: Optional[str] = None
    work_type: str = "full"
    headcount_value: float = 1.0

class ShiftAssignmentUpdate(BaseModel):
    employee_id: int
    date: date
    job_type_id: Optional[int] = None
    work_type: str = "full"

class ScheduleGenerate(BaseModel):
    month: str

class StatusUpdate(BaseModel):
    status: str


# ---- NLP Modification ----

class NlpModifyRequest(BaseModel):
    input_text: str

class NlpModifyResponse(BaseModel):
    log_id: int
    parsed_instruction: Optional[str] = None
    preview_assignments: list[ShiftAssignmentOut] = []
    changes: list[dict] = []

class NlpLogOut(BaseModel):
    id: int
    schedule_id: int
    input_text: str
    parsed_instruction: Optional[str] = None
    status: str


# ---- Reports ----

class EmployeeReportOut(BaseModel):
    employee_id: int
    employee_name: str
    total_work_days: float
    total_days_off: int
    requested_work_days: Optional[str] = None
    job_type_counts: dict[str, float] = {}

class ReportOut(BaseModel):
    month: str
    employees: list[EmployeeReportOut] = []
    fairness_max: float = 0
    fairness_min: float = 0
    fairness_diff: float = 0


# ---- Holidays ----

class HolidayOut(BaseModel):
    date: date
    name: str
