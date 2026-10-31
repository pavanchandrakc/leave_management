import os
from datetime import datetime, date
from typing import Optional, List
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Text,
    select
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    sessionmaker,
    Session
)

# Look for .env in current file's parent or backend folder
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if not os.path.exists(env_path):
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "leave_management_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    department = Column(String(50), nullable=True)
    role = Column(String(20), default="EMPLOYEE")  # 'EMPLOYEE' or 'HR'
    created_at = Column(DateTime, default=datetime.utcnow)

    balances = relationship("LeaveBalance", back_populates="employee", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="employee", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "department": self.department,
            "role": self.role or "EMPLOYEE",
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class LeaveType(Base):
    __tablename__ = "leave_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    default_days_allowed = Column(Integer, default=12)

    balances = relationship("LeaveBalance", back_populates="leave_type", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="leave_type", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "default_days_allowed": self.default_days_allowed
        }


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False)
    total_days = Column(Integer, nullable=False)
    used_days = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("employee_id", "leave_type_id", name="unique_employee_leave_type"),
    )

    employee = relationship("Employee", back_populates="balances")
    leave_type = relationship("LeaveType", back_populates="balances")

    @property
    def remaining_days(self) -> int:
        return (self.total_days or 0) - (self.used_days or 0)

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "leave_type_id": self.leave_type_id,
            "leave_type": self.leave_type.name if self.leave_type else None,
            "total_days": self.total_days,
            "used_days": self.used_days,
            "remaining_days": self.remaining_days
        }


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(String(20), default="PENDING")
    applied_at = Column(DateTime, default=datetime.utcnow)
    decision_notes = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')", name="check_valid_status"),
    )

    employee = relationship("Employee", back_populates="leave_requests")
    leave_type = relationship("LeaveType", back_populates="leave_requests")

    @property
    def days(self) -> int:
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0

    def to_dict(self):
        return {
            "request_id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.name if self.employee else None,
            "department": self.employee.department if self.employee else None,
            "leave_type": self.leave_type.name if self.leave_type else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "days": self.days,
            "reason": self.reason,
            "status": self.status,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "decision_notes": self.decision_notes
        }


@contextmanager
def get_session():
    """Transactional session context manager."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Automatically create all tables in PostgreSQL and seed initial sample data if empty."""
    Base.metadata.create_all(bind=engine)
    with get_session() as session:
        # Seed leave types if not present
        if session.query(LeaveType).count() == 0:
            leave_types = [
                LeaveType(name="Sick Leave", default_days_allowed=10),
                LeaveType(name="Casual Leave", default_days_allowed=12),
                LeaveType(name="Paid Leave", default_days_allowed=15),
            ]
            session.add_all(leave_types)
            session.flush()

        # Seed sample employees if not present
        if session.query(Employee).count() == 0:
            emp1 = Employee(name="John Doe", email="john.doe@example.com", department="Engineering", role="EMPLOYEE")
            emp2 = Employee(name="Jane Smith", email="jane.smith@example.com", department="Design", role="EMPLOYEE")
            hr1 = Employee(name="Sarah Connor", email="sarah.hr@example.com", department="Human Resources", role="HR")
            session.add_all([emp1, emp2, hr1])
            session.flush()

            # Seed balances for all employees for all leave types
            all_types = session.query(LeaveType).all()
            for emp in [emp1, emp2, hr1]:
                for lt in all_types:
                    balance = LeaveBalance(
                        employee_id=emp.id,
                        leave_type_id=lt.id,
                        total_days=lt.default_days_allowed,
                        used_days=0
                    )
                    session.add(balance)
