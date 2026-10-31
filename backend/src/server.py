import json
import csv
import io
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import FastMCP
from src.models import (
    get_session,
    init_db,
    Employee,
    LeaveType,
    LeaveBalance,
    LeaveRequest,
    Holiday
)
from src.leave_engine import calculate_leave_days

mcp = FastMCP("leave-management")

def to_json(data: Any) -> str:
    return json.dumps(data, indent=2)

@mcp.tool()
def setup_database() -> str:
    """Initialize database tables and default seed data in PostgreSQL."""
    try:
        init_db()
        return "Database tables and initial seed data created successfully!"
    except Exception as e:
        return f"Error initializing database: {str(e)}"

@mcp.tool()
def list_holidays(year: Optional[int] = None) -> str:
    """List official company public holidays with optional year filter."""
    with get_session() as session:
        q = session.query(Holiday)
        if year:
            q = q.filter(
                Holiday.holiday_date >= date(year, 1, 1),
                Holiday.holiday_date <= date(year, 12, 31)
            )
        holidays = q.order_by(Holiday.holiday_date.asc()).all()
        return to_json([h.to_dict() for h in holidays])

@mcp.tool()
def add_holiday(name: str, holiday_date: str, description: Optional[str] = None) -> str:
    """Add a new company holiday (holiday_date format: 'YYYY-MM-DD')."""
    try:
        h_date = datetime.strptime(holiday_date.strip(), "%Y-%m-%d").date()
    except ValueError:
        return "Error: holiday_date must be in YYYY-MM-DD format."

    with get_session() as session:
        existing = session.query(Holiday).filter(Holiday.holiday_date == h_date).first()
        if existing:
            return f"Error: A holiday already exists on {h_date} ('{existing.name}')."

        h = Holiday(name=name.strip(), holiday_date=h_date, description=description)
        session.add(h)
        session.flush()
        return to_json({
            "message": f"Holiday '{h.name}' on {h.holiday_date} added successfully.",
            "holiday": h.to_dict()
        })

@mcp.tool()
def get_leave_balances(employee_id: Optional[int] = None, email: Optional[str] = None) -> str:
    """Get the leave balances for an employee using either employee_id or email."""
    if not employee_id and not email:
        return "Error: Please provide either employee_id or email."

    with get_session() as session:
        query = session.query(Employee)
        if employee_id:
            emp = query.filter(Employee.id == employee_id).first()
        else:
            emp = query.filter(Employee.email.ilike(email.strip())).first()

        if not emp:
            return f"Error: No employee found matching {'ID ' + str(employee_id) if employee_id else 'email ' + email}."

        balances_data = []
        for bal in emp.balances:
            balances_data.append({
                "leave_type": bal.leave_type.name,
                "total_days": bal.total_days,
                "used_days": bal.used_days,
                "remaining_days": bal.remaining_days,
                "max_consecutive_days": bal.leave_type.max_consecutive_days
            })

        return to_json({
            "employee_id": emp.id,
            "employee_name": emp.name,
            "email": emp.email,
            "department": emp.department,
            "role": emp.role,
            "leave_balances": balances_data
        })

@mcp.tool()
def calculate_leave_duration(leave_type_name: str, start_date: str, end_date: str) -> str:
    """Preview working days and policy breakdown for a date range (excludes weekends and public holidays)."""
    try:
        s_date = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
        e_date = datetime.strptime(end_date.strip(), "%Y-%m-%d").date()
    except ValueError:
        return "Error: Dates must be in YYYY-MM-DD format."

    if e_date < s_date:
        return "Error: end_date cannot be earlier than start_date."

    with get_session() as session:
        lt = session.query(LeaveType).filter(LeaveType.name.ilike(leave_type_name.strip())).first()
        if not lt:
            return f"Error: Leave type '{leave_type_name}' not found."

        deductible_days, breakdown = calculate_leave_days(session, s_date, e_date, lt)
        calendar_days = (e_date - s_date).days + 1

        return to_json({
            "leave_type": lt.name,
            "start_date": s_date.isoformat(),
            "end_date": e_date.isoformat(),
            "calendar_days": calendar_days,
            "deductible_days": deductible_days,
            "breakdown": breakdown,
            "max_consecutive_days": lt.max_consecutive_days
        })

@mcp.tool()
def apply_leave(
    employee_id: int,
    leave_type_name: str,
    start_date: str,
    end_date: str,
    reason: str
) -> str:
    """Submit a new leave request (Dates: 'YYYY-MM-DD'). Excludes weekends & public holidays."""
    try:
        s_date = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
        e_date = datetime.strptime(end_date.strip(), "%Y-%m-%d").date()
    except ValueError:
        return "Error: Dates must be in YYYY-MM-DD format."

    if e_date < s_date:
        return "Error: end_date cannot be earlier than start_date."

    with get_session() as session:
        emp = session.query(Employee).filter(Employee.id == employee_id).first()
        if not emp:
            return f"Error: Employee with ID {employee_id} not found."

        lt = session.query(LeaveType).filter(LeaveType.name.ilike(leave_type_name.strip())).first()
        if not lt:
            return f"Error: Leave type '{leave_type_name}' does not exist."

        # 1. Overlapping leave check
        overlap = session.query(LeaveRequest).filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status.in_(["PENDING", "APPROVED"]),
            LeaveRequest.start_date <= e_date,
            LeaveRequest.end_date >= s_date
        ).first()

        if overlap:
            return f"Error: Overlapping leave request #{overlap.id} found ({overlap.start_date} to {overlap.end_date}, status: {overlap.status})."

        # 2. Leave Engine working days calculation
        deductible_days, breakdown = calculate_leave_days(session, s_date, e_date, lt)
        if deductible_days == 0:
            return "Error: Selected date range contains 0 working days (dates fall on weekends or public holidays)."

        # 3. Policy rule check
        if lt.max_consecutive_days and deductible_days > lt.max_consecutive_days:
            return f"Error: {lt.name} allows a maximum of {lt.max_consecutive_days} consecutive working day(s), but {deductible_days} were requested."

        # 4. Balance check
        bal = session.query(LeaveBalance).filter(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type_id == lt.id
        ).first()

        if not bal:
            return f"Error: No balance record found for employee ID {employee_id} and leave type '{leave_type_name}'."

        if bal.remaining_days < deductible_days:
            return f"Error: Insufficient balance. Requested {deductible_days} working day(s), but only {bal.remaining_days} remaining."

        req = LeaveRequest(
            employee_id=emp.id,
            leave_type_id=lt.id,
            start_date=s_date,
            end_date=e_date,
            deductible_days=deductible_days,
            reason=reason,
            status="PENDING"
        )
        session.add(req)
        session.flush()

        return to_json({
            "message": "Leave request submitted successfully.",
            "request_id": req.id,
            "employee_name": emp.name,
            "leave_type": lt.name,
            "working_days": deductible_days,
            "calendar_days": (e_date - s_date).days + 1,
            "status": req.status,
            "applied_at": req.applied_at.isoformat(),
            "breakdown": breakdown
        })

@mcp.tool()
def list_leave_requests(status: Optional[str] = None, employee_id: Optional[int] = None) -> str:
    """List leave requests with optional filters ('PENDING', 'APPROVED', etc.)."""
    with get_session() as session:
        query = session.query(LeaveRequest)
        if status:
            query = query.filter(LeaveRequest.status.ilike(status.strip()))
        if employee_id:
            query = query.filter(LeaveRequest.employee_id == employee_id)

        requests = query.order_by(LeaveRequest.applied_at.desc()).all()
        return to_json([r.to_dict() for r in requests])

@mcp.tool()
def update_leave_status(request_id: int, status: str, notes: Optional[str] = None) -> str:
    """Approve, reject, or cancel a leave request. If approved, deducts working days; if cancelled, restores balance."""
    status_upper = status.strip().upper()
    if status_upper not in ("APPROVED", "REJECTED", "CANCELLED"):
        return "Error: Status must be 'APPROVED', 'REJECTED', or 'CANCELLED'."

    with get_session() as session:
        req = session.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
        if not req:
            return f"Error: Leave request with ID {request_id} not found."

        if req.deductible_days is not None:
            req_days = req.deductible_days
        else:
            req_days, _ = calculate_leave_days(session, req.start_date, req.end_date, req.leave_type)
            req.deductible_days = req_days

        bal = session.query(LeaveBalance).filter(
            LeaveBalance.employee_id == req.employee_id,
            LeaveBalance.leave_type_id == req.leave_type_id
        ).with_for_update().first()

        if not bal:
            return f"Error: Balance record not found for employee {req.employee_id} and leave type {req.leave_type_id}."

        if status_upper == "APPROVED":
            if req.status != "PENDING":
                return f"Error: Cannot approve request with status '{req.status}'."

            remaining = (bal.total_days or 0) - (bal.used_days or 0)
            if remaining < req_days:
                return f"Error: Cannot approve request #{request_id}. Employee only has {remaining} day(s) remaining for {req.leave_type.name}, but {req_days} working day(s) are required."

            bal.used_days = (bal.used_days or 0) + req_days

        elif status_upper == "CANCELLED":
            if req.status == "APPROVED":
                bal.used_days = max(0, (bal.used_days or 0) - req_days)
            elif req.status != "PENDING":
                return f"Error: Cannot cancel request with status '{req.status}'."

        elif status_upper == "REJECTED":
            if req.status != "PENDING":
                return f"Error: Cannot reject request with status '{req.status}'."

        req.status = status_upper
        req.decision_notes = notes

        return to_json({
            "message": f"Leave request #{request_id} successfully {status_upper}.",
            "request_id": req.id,
            "status": req.status,
            "days_deducted": req_days if status_upper == "APPROVED" else 0,
            "decision_notes": req.decision_notes
        })

@mcp.tool()
def get_team_leaves(start_date: str, end_date: str, department: Optional[str] = None) -> str:
    """Find team members on approved leave in a date window."""
    try:
        s_date = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
        e_date = datetime.strptime(end_date.strip(), "%Y-%m-%d").date()
    except ValueError:
        return "Error: Dates must be in YYYY-MM-DD format."

    with get_session() as session:
        query = session.query(LeaveRequest).join(Employee).filter(
            LeaveRequest.status == "APPROVED",
            LeaveRequest.start_date <= e_date,
            LeaveRequest.end_date >= s_date
        )
        if department:
            query = query.filter(Employee.department.ilike(department.strip()))

        results = query.order_by(LeaveRequest.start_date.asc()).all()
        return to_json([r.to_dict() for r in results])

@mcp.tool()
def generate_monthly_leave_report(year: int, month: int, format: str = "json") -> str:
    """Generate leave trends, absenteeism, and department-wise usage for a specific year and month."""
    import calendar
    _, last_day = calendar.monthrange(year, month)
    m_start = date(year, month, 1)
    m_end = date(year, month, last_day)

    with get_session() as session:
        requests = session.query(LeaveRequest).join(Employee).join(LeaveType).filter(
            LeaveRequest.start_date <= m_end,
            LeaveRequest.end_date >= m_start
        ).all()

        dept_usage: Dict[str, int] = {}
        type_usage: Dict[str, int] = {}
        status_counts: Dict[str, int] = {"PENDING": 0, "APPROVED": 0, "REJECTED": 0, "CANCELLED": 0}
        total_days_taken = 0

        rows = []
        for r in requests:
            dept = r.employee.department or "General"
            lt_name = r.leave_type.name
            st = r.status.upper()
            status_counts[st] = status_counts.get(st, 0) + 1

            if st == "APPROVED":
                dept_usage[dept] = dept_usage.get(dept, 0) + r.days
                type_usage[lt_name] = type_usage.get(lt_name, 0) + r.days
                total_days_taken += r.days

            rows.append({
                "Request_ID": r.id,
                "Employee_Name": r.employee.name,
                "Department": dept,
                "Leave_Type": lt_name,
                "Start_Date": r.start_date.isoformat(),
                "End_Date": r.end_date.isoformat(),
                "Working_Days": r.days,
                "Status": r.status,
                "Reason": r.reason or "",
                "Decision_Notes": r.decision_notes or ""
            })

        if format.lower() == "csv":
            output = io.StringIO()
            if rows:
                writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            else:
                output.write("No leave requests found for this period.")
            return output.getvalue()

        return to_json({
            "year": year,
            "month": month,
            "summary": {
                "total_requests": len(requests),
                "total_days_approved": total_days_taken,
                "status_counts": status_counts,
                "department_usage_days": dept_usage,
                "leave_type_usage_days": type_usage
            },
            "records": rows
        })

if __name__ == "__main__":
    init_db()
    mcp.run(transport="stdio")
