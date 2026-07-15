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

# 本番環境（PORT設定あり）でSQLiteを使用している場合は警告
if _is_sqlite and os.getenv("PORT"):
    logger.warning(
        "⚠️ SQLiteを本番環境で使用中。データはデプロイ時に消失します。"
        "DATABASE_URLにPostgreSQLを設定してください。"
    )

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
    staff_token = Column(Text, nullable=True, unique=True)
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
    sort_order = Column(Integer, nullable=False, default=0)


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
    weekly_work_day_limit = Column(Integer, nullable=True)
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
    comment = Column(Text, nullable=True, default="")

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


class RequestBackup(Base):
    __tablename__ = "request_backups"
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    target_month = Column(Text, nullable=False)
    backup_data = Column(Text, nullable=False)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee")


class CompanyHoliday(Base):
    """会社の臨時休業日（年末年始・お盆など）。祝日・土日と同様に非営業日として扱う。"""
    __tablename__ = "company_holidays"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True)
    name = Column(Text, nullable=False, default="臨時休業")
    created_at = Column(DateTime, default=datetime.utcnow)


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


def _migrate_add_weekly_work_day_limit():
    """Add weekly_work_day_limit column to shift_requests if it doesn't exist."""
    try:
        columns = _get_existing_columns("shift_requests")
        if columns and "weekly_work_day_limit" not in columns:
            with engine.begin() as conn:
                conn.execute(sa_text(
                    "ALTER TABLE shift_requests ADD COLUMN weekly_work_day_limit INTEGER"
                ))
    except Exception:
        pass  # Table may not exist yet


def _migrate_add_job_type_sort_order():
    """Add sort_order column to job_types and set correct display order."""
    try:
        columns = _get_existing_columns("job_types")
        if not columns:
            return
        if "sort_order" not in columns:
            with engine.begin() as conn:
                conn.execute(sa_text(
                    "ALTER TABLE job_types ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
                ))
        # Always ensure correct sort_order and color values by name
        desired = {
            "職人":       (1, "#FF6B6B"),
            "サブ職人":   (2, "#4DABF7"),
            "lkデータ":   (3, "#51CF66"),
            "uv/cpデータ": (4, "#CC5DE8"),
            "手紙":       (5, "#F59F00"),
            "その他":     (6, "#FFD43B"),
        }
        with engine.begin() as conn:
            for name, (order, color) in desired.items():
                conn.execute(sa_text(
                    "UPDATE job_types SET sort_order = :order, color = :color WHERE name = :name"
                ), {"order": order, "color": color, "name": name})
    except Exception:
        pass


def _migrate_split_data_job_type():
    """Rename 'データ' to 'lkデータ' and add 'uv/cデータ' job type.
    Auto-assign 'uv/cデータ' to all employees who had 'データ'."""
    try:
        inspector = sa_inspect(engine)
        if "job_types" not in inspector.get_table_names():
            return
        with engine.begin() as conn:
            # Check if 'データ' exists and 'lkデータ' does not
            row = conn.execute(sa_text(
                "SELECT id FROM job_types WHERE name = 'データ'"
            )).fetchone()
            if row is None:
                return  # Already migrated or no data job type
            lk_check = conn.execute(sa_text(
                "SELECT id FROM job_types WHERE name = 'lkデータ'"
            )).fetchone()
            if lk_check is not None:
                return  # Already migrated

            data_id = row[0]
            # Rename データ → lkデータ with new color
            conn.execute(sa_text(
                "UPDATE job_types SET name = 'lkデータ', color = '#51CF66' WHERE id = :id"
            ), {"id": data_id})

            # Add uv/cデータ
            conn.execute(sa_text(
                "INSERT INTO job_types (name, color) VALUES ('uv/cデータ', '#CC5DE8')"
            ))
            uvc_row = conn.execute(sa_text(
                "SELECT id FROM job_types WHERE name = 'uv/cデータ'"
            )).fetchone()
            if uvc_row is None:
                return
            uvc_id = uvc_row[0]

            # Auto-assign uv/cデータ to all employees who had データ (now lkデータ)
            emp_rows = conn.execute(sa_text(
                "SELECT employee_id FROM employee_job_types WHERE job_type_id = :jt_id"
            ), {"jt_id": data_id}).fetchall()
            for emp_row in emp_rows:
                conn.execute(sa_text(
                    "INSERT INTO employee_job_types (employee_id, job_type_id) VALUES (:emp_id, :jt_id)"
                ), {"emp_id": emp_row[0], "jt_id": uvc_id})
    except Exception:
        pass


def _migrate_add_staff_token():
    """Add staff_token column to employees if it doesn't exist."""
    try:
        columns = _get_existing_columns("employees")
        if columns and "staff_token" not in columns:
            with engine.begin() as conn:
                conn.execute(sa_text(
                    "ALTER TABLE employees ADD COLUMN staff_token TEXT"
                ))
    except Exception:
        pass  # Table may not exist yet


def _migrate_rename_uvc_and_add_tegami():
    """Rename 'uv/cデータ' to 'uv/cpデータ' and add '手紙' job type."""
    try:
        inspector = sa_inspect(engine)
        if "job_types" not in inspector.get_table_names():
            return
        with engine.begin() as conn:
            # Rename uv/cデータ → uv/cpデータ
            row = conn.execute(sa_text(
                "SELECT id FROM job_types WHERE name = 'uv/cデータ'"
            )).fetchone()
            if row is not None:
                conn.execute(sa_text(
                    "UPDATE job_types SET name = 'uv/cpデータ' WHERE id = :id"
                ), {"id": row[0]})

            # Add 手紙 if it doesn't exist
            tegami = conn.execute(sa_text(
                "SELECT id FROM job_types WHERE name = '手紙'"
            )).fetchone()
            if tegami is None:
                conn.execute(sa_text(
                    "INSERT INTO job_types (name, color, sort_order) VALUES ('手紙', '#F59F00', 5)"
                ))
    except Exception:
        pass


def _migrate_add_schedule_comment():
    """Add comment column to schedules if it doesn't exist."""
    try:
        columns = _get_existing_columns("schedules")
        if columns and "comment" not in columns:
            with engine.begin() as conn:
                conn.execute(sa_text(
                    "ALTER TABLE schedules ADD COLUMN comment TEXT DEFAULT ''"
                ))
    except Exception:
        pass


def init_db():
    """Create tables and seed initial data."""
    Base.metadata.create_all(bind=engine)
    _migrate_add_period_column()
    _migrate_add_employment_type()
    _migrate_work_days_to_text()
    _migrate_add_sort_order()
    _migrate_add_weekly_work_day_limit()
    _migrate_split_data_job_type()
    _migrate_rename_uvc_and_add_tegami()
    _migrate_add_staff_token()
    _migrate_add_job_type_sort_order()
    _migrate_add_schedule_comment()
    db = SessionLocal()
    try:
        if db.query(JobType).count() == 0:
            seed_job_types = [
                JobType(name="職人", color="#FF6B6B", sort_order=1),
                JobType(name="サブ職人", color="#4DABF7", sort_order=2),
                JobType(name="lkデータ", color="#51CF66", sort_order=3),
                JobType(name="uv/cpデータ", color="#CC5DE8", sort_order=4),
                JobType(name="手紙", color="#F59F00", sort_order=5),
                JobType(name="その他", color="#FFD43B", sort_order=6),
            ]
            db.add_all(seed_job_types)
            db.commit()

        if db.query(Employee).count() == 0:
            # name, employment_type, job_type_names
            seed_data = [
                ("部長",       "full_time", ["その他"]),
                ("岩生亜紀子", "full_time", ["その他"]),
                ("大野千絵美", "full_time", ["職人", "サブ職人", "lkデータ", "uv/cpデータ", "手紙", "その他"]),
                ("和平映美",   "full_time", ["職人", "サブ職人", "lkデータ", "uv/cpデータ", "手紙", "その他"]),
                ("岡崎智恵子", "full_time", ["職人"]),
                ("川上節子",   "dependent", ["lkデータ", "uv/cpデータ", "手紙", "その他"]),
                ("植原ふみ代", "full_time", ["職人", "サブ職人", "lkデータ", "手紙", "その他"]),
                ("尾崎慶子",   "dependent", ["手紙", "その他"]),
                ("酒向邦江",   "dependent", ["手紙", "その他"]),
                ("カンサ萌",   "dependent", ["lkデータ", "uv/cpデータ", "手紙", "その他"]),
                ("秋山智子",   "dependent", ["手紙", "その他"]),
                ("石原圭子",   "full_time", ["lkデータ", "手紙", "その他"]),
                ("工藤友里",   "full_time", ["lkデータ", "手紙", "その他"]),
                ("近藤美佐子", "full_time", ["手紙", "その他"]),
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
