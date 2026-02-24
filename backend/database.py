from sqlalchemy import (
    create_engine, Column, Integer, Text, DateTime, Date, Float, ForeignKey,
    event
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shift_scheduler.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Enable WAL mode and foreign keys for SQLite
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
    requested_work_days = Column(Integer)
    requested_days_off = Column(Integer)
    note = Column(Text)

    employee = relationship("Employee", back_populates="shift_requests")
    details = relationship("RequestDetail", back_populates="shift_request", cascade="all, delete-orphan")


class RequestDetail(Base):
    __tablename__ = "request_details"
    id = Column(Integer, primary_key=True, autoincrement=True)
    shift_request_id = Column(Integer, ForeignKey("shift_requests.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)

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


def init_db():
    """Create tables and seed initial data."""
    Base.metadata.create_all(bind=engine)
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
    finally:
        db.close()
