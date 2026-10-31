import json
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
    """
    Initialize database tables and default seed data automatically in PostgreSQL.
    Can be run directly from Claude if tables are not yet created in pgAdmin.
    """
    try:
        init_db()
        return "Database tables and initial seed data created successfully!"
    except Exception as e:
        return f"Error initializing database: {str(e)}"

@mcp.tool()
def get_leave_balances(employee_id: Optional[int] = None, email: Optional[str] = None) -> str:
    """
    Get the leave balances for an employee using either their employee_id or email.
    """
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
    """
    Submit a new leave request.
    Dates must be in 'YYYY-MM-DD' format.
    """
    try:
        s_date = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
        e_date = datetime.strptime(end_date.strip(), "%Y-%m-%d").date()
    except ValueError:
        return "Error: Dates must be in YYYY-MM-DD format."

    if e_date < s_date:
        return "Error: end_date cannot be earlier than start_date."

    days_requested = (e_date - s_date).days + 1

    with get_session() as session:
        # Check employee
        emp = session.query(Employee).filter(Employee.id == employee_id).first()
        if not emp:
            return f"Error: Employee with ID {employee_id} not found."

        # Check leave type
        lt = session.query(LeaveType).filter(LeaveType.name.ilike(leave_type_name.strip())).first()
        if not lt:
            return f"Error: Leave type '{leave_type_name}' does not exist."

        # Check balance
        bal = session.query(LeaveBalance).filter(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type_id == lt.id
        ).first()

        if not bal:
            return f"Error: No balance record found for employee ID {employee_id} and leave type '{leave_type_name}'."

        if bal.remaining_days < days_requested:
            return f"Warning: Requested {days_requested} day(s), but only {bal.remaining_days} day(s) remaining."

        # Create request
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
    """
    List leave requests with optional filters:
    - status: 'PENDING', 'APPROVED', 'REJECTED', 'CANCELLED'
    - employee_id: filter by a specific employee's ID
    """
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
    """
    Approve or reject a leave request.
    Valid status values: 'APPROVED', 'REJECTED'
    If approved, automatically deducts from the employee's leave balance in PostgreSQL.
    """
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
    """
    Find which team members are on approved leave during a given date window.
    Dates must be in 'YYYY-MM-DD' format.
    """
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

if __name__ == "__main__":
    # Ensure tables exist on server startup
    init_db()
    mcp.run(transport="stdio")
