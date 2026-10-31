import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.models import engine, Employee, LeaveType, LeaveBalance, get_session
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE employees ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'EMPLOYEE';"))
        conn.commit()
        print("Role column migrated successfully.")

    with get_session() as s:
        hr = s.query(Employee).filter(Employee.email == "sarah.hr@example.com").first()
        if not hr:
            hr = Employee(name="Sarah Connor (HR)", email="sarah.hr@example.com", department="Human Resources", role="HR")
            s.add(hr)
            s.flush()
            for lt in s.query(LeaveType).all():
                s.add(LeaveBalance(employee_id=hr.id, leave_type_id=lt.id, total_days=lt.default_days_allowed, used_days=0))
            print("Created HR Admin user: Sarah Connor (HR)")

if __name__ == "__main__":
    migrate()
