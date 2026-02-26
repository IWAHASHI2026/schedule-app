from sqlalchemy import (
    create_engine, Column, Integer, Text, DateTime, Date, Float, ForeignKey,
    event, inspect as sa_inspect, text as sa_text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from datetime import datetime, date
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shift_scheduler.db")

# Railway provides postgres:// but SQLAlchemy requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_is_sqlite = DATABASE_URL.startswith("sqlite")

# SQLite needs check_same_thread=False; PostgreSQL does not
_engine_kwargs = {}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Enable WAL mode and foreign keys for SQLite only
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---- ORM Models ----

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    employment_type = Column(Text, nullable=False, default="full_time")
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job_types = relationship("EmployeeJobType", back_populates="employee", cascade="all, delete-orphan")
    shift_requests = relationship("ShiftRequest", back_populates="employee", cascade="all, delete-orphan")
    shift_assignments = relationship("ShiftAssignment", back_populates="employee", cascade="all, delete-orphan")


class JobType(Base):
    __tablename__ = "job_types"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    color = Column(Text)


class EmployeeJobType(Base):
    __tablename__ = "employee_job_types"
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    job_type_id = Column(Integer, ForeignKey("job_types.id"), nullable=False)

    employee = relationship("Employee", back_populates="job_types")
    job_type = relationship("JobType")


class ShiftRequest(Base):
    __tablename__ = "shift_requests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    target_month = Column(Text, nullable=False)
    requested_work_days = Column(Text)  # "1"-"23" or "max"
    note = Column(Text)

    employee = relationship("Employee", back_populates="shift_requests")
    details = relationship("RequestDetail", back_populates="shift_request", cascade="all, delete-orphan")


class RequestDetail(Base):
    __tablename__ = "request_details"
    id = Column(Integer, primary_key=True, autoincrement=True)
    shift_request_id = Column(Integer, ForeignKey("shift_requests.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    period = Column(Text, nullable=False, default="all_day")  # "am", "pm", or "all_day"

    shift_request = relationship("ShiftRequest", back_populates="details")


class DailyRequirement(Base):
    __tablename__ = "daily_requirements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    job_type_id = Column(Integer, ForeignKey("job_types.id"), nullable=False)
    required_count = Column(Float, nullable=False)

    job_type = relationship("JobType")


class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    target_month = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="draft")
    generated_at = Column(DateTime)
    confirmed_at = Column(DateTime)

    assignments = relationship("ShiftAssignment", back_populates="schedule", cascade="all, delete-orphan")
    nlp_logs = relationship("NlpModificationLog", back_populates="schedule", cascade="all, delete-orphan")


class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    job_type_id = Column(Integer, ForeignKey("job_types.id"), nullable=True)
    work_type = Column(Text, nullable=False, default="full")
    headcount_value = Column(Float, nullable=False, default=1.0)

    schedule = relationship("Schedule", back_populates="assignments")
    employee = relationship("Employee", back_populates="shift_assignments")
    job_type = relationship("JobType")


class NlpModificationLog(Base):
    __tablename__ = "nlp_modification_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False)
    input_text = Column(Text, nullable=False)
    parsed_instruction = Column(Text)
    status = Column(Text, nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    schedule = relationship("Schedule", back_populates="nlp_logs")


def _get_existing_columns(table_name: str) -> list[str]:
    """Get existing column names for a table using SQLAlchemy inspect."""
    try:
        inspector = sa_inspect(engine)
        if table_name not in inspector.get_table_names():
            return []
        return [col["name"] for col in inspector.get_columns(table_name)]
    except Exception:
        return []


def _migrate_add_period_column():
    """Add period column to request_details if it doesn't exist."""
    try:
        columns = _get_existing_columns("request_details")
        if columns and "period" not in columns:
            with engine.begin() as conn:
                conn.execute(sa_text(
                    "ALTER TABLE request_details ADD COLUMN period TEXT NOT NULL DEFAULT 'all_day'"
                ))
    except Exception:
        pass  # Table may not exist yet


def _migrate_add_employment_type():
    """Add employment_type column to employees if it doesn't exist."""
    try:
        columns = _get_existing_columns("employees")
        if columns and "employment_type" not in columns:
            with engine.begin() as conn:
                conn.execute(sa_text(
                    "ALTER TABLE employees ADD COLUMN employment_type TEXT NOT NULL DEFAULT 'full_time'"
                ))
    except Exception:
        pass  # Table may not exist yet


def _migrate_work_days_to_text():
    """Convert requested_work_days from integer to text in shift_requests."""
    if not _is_sqlite:
        return  # PostgreSQL text columns don't need this migration
    try:
        columns = _get_existing_columns("shift_requests")
        if columns and "requested_work_days" in columns:
            with engine.begin() as conn:
                conn.execute(sa_text(
                    "UPDATE shift_requests SET requested_work_days = CAST(requested_work_days AS TEXT) "
                    "WHERE requested_work_days IS NOT NULL AND typeof(requested_work_days) != 'text'"
                ))
    except Exception:
        pass  # Table may not exist yet


def _migrate_add_sort_order():
    """Add sort_order column to employees if it doesn't exist."""
    try:
        columns = _get_existing_columns("employees")
        if columns and "sort_order" not in columns:
            with engine.begin() as conn:
                conn.execute(sa_text(
                    "ALTER TABLE employees ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
                ))
                # Assign sort_order based on existing id order
                rows = conn.execute(sa_text("SELECT id FROM employees ORDER BY id")).fetchall()
                for idx, row in enumerate(rows):
                    conn.execute(sa_text(
                        "UPDATE employees SET sort_order = :idx WHERE id = :id"
                    ), {"idx": idx, "id": row[0]})
    except Exception:
        pass  # Table may not exist yet


def init_db():
    """Create tables and seed initial data."""
    Base.metadata.create_all(bind=engine)
    _migrate_add_period_column()
    _migrate_add_employment_type()
    _migrate_work_days_to_text()
    _migrate_add_sort_order()
    db = SessionLocal()
    try:
        if db.query(JobType).count() == 0:
            seed_job_types = [
                JobType(name="職人", color="#FF6B6B"),
                JobType(name="サブ職人", color="#4DABF7"),
                JobType(name="データ", color="#51CF66"),
                JobType(name="その他", color="#FFD43B"),
            ]
            db.add_all(seed_job_types)
            db.commit()

        if db.query(Employee).count() == 0:
            # name, employment_type, job_type_names
            seed_data = [
                ("部長",       "full_time", ["その他"]),
                ("若生亜紀子", "full_time", ["その他"]),
                ("和平映美",   "full_time", ["職人", "サブ職人", "データ", "その他"]),
                ("岡崎智恵子", "full_time", ["職人"]),
                ("川上朋子",   "dependent", ["データ", "その他"]),
                ("植原ふみ代", "full_time", ["職人", "サブ職人", "データ", "その他"]),
                ("尾崎廣子",   "dependent", ["データ", "その他"]),
                ("酒向邦江",   "dependent", ["データ", "その他"]),
                ("カンサ萌",   "dependent", ["データ", "その他"]),
                ("秋山智子",   "dependent", ["その他"]),
                ("石原圭子",   "full_time", ["データ", "その他"]),
                ("工藤友里",   "full_time", ["データ", "その他"]),
                ("近藤美佐子", "full_time", ["データ", "その他"]),
                ("大野千絵美", "full_time", ["職人", "サブ職人", "データ", "その他"]),
            ]
            jt_map = {jt.name: jt.id for jt in db.query(JobType).all()}
            for idx, (name, emp_type, jt_names) in enumerate(seed_data):
                emp = Employee(name=name, employment_type=emp_type, sort_order=idx)
                db.add(emp)
                db.flush()
                for jt_name in jt_names:
                    if jt_name in jt_map:
                        db.add(EmployeeJobType(employee_id=emp.id, job_type_id=jt_map[jt_name]))
            db.commit()
    finally:
        db.close()


def cleanup_old_schedules(db: Session | None = None) -> int:
    """13ヶ月より古いスケジュールと関連データを削除する。

    カスケード削除により ShiftAssignment, NlpModificationLog,
    RequestDetail も自動的に削除される。
    """
    close_after = False
    if db is None:
        db = SessionLocal()
        close_after = True

    try:
        today = date.today()
        cutoff_month = today.month - 13
        cutoff_year = today.year
        while cutoff_month <= 0:
            cutoff_month += 12
            cutoff_year -= 1
        cutoff_str = f"{cutoff_year:04d}-{cutoff_month:02d}"

        # 古いスケジュールを削除（ShiftAssignment, NlpModificationLog はカスケード削除）
        old_schedules = (
            db.query(Schedule)
            .filter(Schedule.target_month < cutoff_str)
            .all()
        )
        schedule_count = len(old_schedules)
        if schedule_count > 0:
            deleted_months = sorted(set(s.target_month for s in old_schedules))
            for schedule in old_schedules:
                db.delete(schedule)
            logger.info(
                "保管期限クリーンアップ: %d件のスケジュールを削除 (対象月: %s)",
                schedule_count, ", ".join(deleted_months),
            )

        # 古いシフト希望を削除（RequestDetail はカスケード削除）
        old_requests = (
            db.query(ShiftRequest)
            .filter(ShiftRequest.target_month < cutoff_str)
            .all()
        )
        request_count = len(old_requests)
        if request_count > 0:
            for req in old_requests:
                db.delete(req)
            logger.info(
                "保管期限クリーンアップ: %d件のシフト希望を削除", request_count,
            )

        # 古い日別必要人数を削除
        cutoff_date = date(cutoff_year, cutoff_month, 1)
        req_count = (
            db.query(DailyRequirement)
            .filter(DailyRequirement.date < cutoff_date)
            .delete()
        )
        if req_count > 0:
            logger.info(
                "保管期限クリーンアップ: %d件の日別必要人数を削除", req_count,
            )

        if schedule_count > 0 or request_count > 0 or req_count > 0:
            db.commit()
        else:
            logger.debug("保管期限クリーンアップ: 削除対象なし (カットオフ: %s)", cutoff_str)

        return schedule_count + request_count + req_count
    except Exception:
        db.rollback()
        logger.exception("保管期限クリーンアップに失敗しました")
        raise
    finally:
        if close_after:
            db.close()
