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
    LeaveRequest
)

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
                "remaining_days": bal.remaining_days
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
def apply_leave(
    employee_id: int,
    leave_type_name: str,
    start_date: str,
    end_date: str,
    reason: str
) -> str:
    """Submit a new leave request (Dates: 'YYYY-MM-DD')."""
    try:
        s_date = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
        e_date = datetime.strptime(end_date.strip(), "%Y-%m-%d").date()
    except ValueError:
        return "Error: Dates must be in YYYY-MM-DD format."

    if e_date < s_date:
        return "Error: end_date cannot be earlier than start_date."

    days_requested = (e_date - s_date).days + 1

    with get_session() as session:
        emp = session.query(Employee).filter(Employee.id == employee_id).first()
        if not emp:
            return f"Error: Employee with ID {employee_id} not found."

        lt = session.query(LeaveType).filter(LeaveType.name.ilike(leave_type_name.strip())).first()
        if not lt:
            return f"Error: Leave type '{leave_type_name}' does not exist."

        bal = session.query(LeaveBalance).filter(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type_id == lt.id
        ).first()

        if not bal:
            return f"Error: No balance record found for employee ID {employee_id} and leave type '{leave_type_name}'."

        if bal.remaining_days < days_requested:
            return f"Warning: Requested {days_requested} day(s), but only {bal.remaining_days} day(s) remaining."

        req = LeaveRequest(
            employee_id=emp.id,
            leave_type_id=lt.id,
            start_date=s_date,
            end_date=e_date,
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
            "days_requested": days_requested,
            "status": req.status,
            "applied_at": req.applied_at.isoformat()
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
    """Approve or reject a leave request. If approved, deducts from employee balance."""
    status_upper = status.strip().upper()
    if status_upper not in ("APPROVED", "REJECTED"):
        return "Error: Status must be either 'APPROVED' or 'REJECTED'."

    with get_session() as session:
        req = session.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
        if not req:
            return f"Error: Leave request with ID {request_id} not found."

        if req.status != "PENDING":
            return f"Error: Request has already been processed with status '{req.status}'."

        if status_upper == "APPROVED":
            bal = session.query(LeaveBalance).filter(
                LeaveBalance.employee_id == req.employee_id,
                LeaveBalance.leave_type_id == req.leave_type_id
            ).first()
            if bal:
                bal.used_days = (bal.used_days or 0) + req.days

        req.status = status_upper
        req.decision_notes = notes

        return to_json({
            "message": f"Leave request #{request_id} successfully {status_upper}.",
            "request_id": req.id,
            "status": req.status,
            "days_deducted": req.days if status_upper == "APPROVED" else 0,
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
    """
    Generate leave trends, absenteeism, and department-wise usage for a specific year and month.
    format: 'json' or 'csv'
    """
    import calendar
    _, last_day = calendar.monthrange(year, month)
    m_start = date(year, month, 1)
    m_end = date(year, month, last_day)

    with get_session() as session:
        # All leaves overlapping this month
        requests = session.query(LeaveRequest).join(Employee).join(LeaveType).filter(
            LeaveRequest.start_date <= m_end,
            LeaveRequest.end_date >= m_start
        ).all()

        dept_usage: Dict[str, int] = {}
        type_usage: Dict[str, int] = {}
        status_counts: Dict[str, int] = {"PENDING": 0, "APPROVED": 0, "REJECTED": 0}
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
                "Days": r.days,
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
