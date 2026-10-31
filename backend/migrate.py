import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.models import engine, Employee, LeaveType, LeaveBalance, Holiday, LeaveRequest, get_session, DEFAULT_HOLIDAYS
from src.leave_engine import calculate_leave_days
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        # 1. Employees role column
        conn.execute(text("ALTER TABLE employees ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'EMPLOYEE';"))
        
        # 2. LeaveType policy columns
        conn.execute(text("ALTER TABLE leave_types ADD COLUMN IF NOT EXISTS counts_weekends BOOLEAN DEFAULT FALSE;"))
        conn.execute(text("ALTER TABLE leave_types ADD COLUMN IF NOT EXISTS counts_holidays BOOLEAN DEFAULT FALSE;"))
        conn.execute(text("ALTER TABLE leave_types ADD COLUMN IF NOT EXISTS max_consecutive_days INT DEFAULT NULL;"))
        conn.execute(text("ALTER TABLE leave_types ADD COLUMN IF NOT EXISTS description VARCHAR(255) DEFAULT NULL;"))
        
        # 3. Holidays table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS holidays (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                holiday_date DATE UNIQUE NOT NULL,
                description VARCHAR(255)
            );
        """))
        
        # 4. LeaveRequest deductible_days column
        conn.execute(text("ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS deductible_days INT DEFAULT NULL;"))

        # 5. LeaveBalances remaining_days STORED GENERATED column & CHECK constraints
        try:
            conn.execute(text("ALTER TABLE leave_balances ADD COLUMN IF NOT EXISTS remaining_days INT GENERATED ALWAYS AS (total_days - used_days) STORED;"))
        except Exception:
            pass

        try:
            conn.execute(text("ALTER TABLE leave_balances ADD CONSTRAINT check_used_days_positive CHECK (used_days >= 0);"))
        except Exception:
            pass

        try:
            conn.execute(text("ALTER TABLE leave_balances ADD CONSTRAINT check_no_overdraft CHECK (used_days <= total_days);"))
        except Exception:
            pass
        
        conn.commit()
        print("Schema altered successfully.")

    with get_session() as s:
        # Update default leave types policies
        casual = s.query(LeaveType).filter(LeaveType.name == "Casual Leave").first()
        if casual:
            casual.counts_weekends = False
            casual.counts_holidays = False
            casual.max_consecutive_days = 3
            casual.description = "Short-term personal time off (max 3 consecutive working days)"

        sick = s.query(LeaveType).filter(LeaveType.name == "Sick Leave").first()
        if sick:
            sick.counts_weekends = False
            sick.counts_holidays = False
            sick.max_consecutive_days = 15
            sick.description = "Medical leave for illness and recovery"

        paid = s.query(LeaveType).filter(LeaveType.name == "Paid Leave").first()
        if paid:
            paid.counts_weekends = False
            paid.counts_holidays = False
            paid.max_consecutive_days = None
            paid.description = "Earned annual vacation leave"

        # Seed holidays if missing
        for h in DEFAULT_HOLIDAYS:
            h_date = datetime.strptime(h["date"], "%Y-%m-%d").date()
            existing = s.query(Holiday).filter(Holiday.holiday_date == h_date).first()
            if not existing:
                s.add(Holiday(name=h["name"], holiday_date=h_date, description=h["description"]))
        print("Holidays seeded/verified.")

        # Ensure HR Admin user exists
        hr = s.query(Employee).filter(Employee.email == "sarah.hr@example.com").first()
        if not hr:
            hr = Employee(name="Sarah Connor (HR)", email="sarah.hr@example.com", department="Human Resources", role="HR")
            s.add(hr)
            s.flush()
            for lt in s.query(LeaveType).all():
                s.add(LeaveBalance(employee_id=hr.id, leave_type_id=lt.id, total_days=lt.default_days_allowed, used_days=0))
            print("Created HR Admin user: Sarah Connor (HR)")

        # Recalculate deductible_days for existing requests if any
        for req in s.query(LeaveRequest).all():
            if req.deductible_days is None:
                days, _ = calculate_leave_days(s, req.start_date, req.end_date, req.leave_type)
                req.deductible_days = days

    print("Migration and data verification complete.")

if __name__ == "__main__":
    migrate()
