import io
import csv
import calendar
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.models import (
    get_session,
    init_db,
    Employee,
    LeaveType,
    LeaveBalance,
    LeaveRequest
)

app = FastAPI(title="Leave Management API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

# Request Models
class ApplyLeaveDTO(BaseModel):
    employee_id: int
    leave_type_name: str
    start_date: str
    end_date: str
    reason: str

class UpdateStatusDTO(BaseModel):
    status: str
    notes: Optional[str] = None

# 1. Employees & Auth Helper
@app.get("/api/employees")
def list_employees():
    with get_session() as session:
        emps = session.query(Employee).order_by(Employee.id).all()
        return [e.to_dict() for e in emps]

@app.get("/api/employees/{employee_id}")
def get_employee(employee_id: int):
    with get_session() as session:
        emp = session.query(Employee).filter(Employee.id == employee_id).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        balances = []
        for b in emp.balances:
            balances.append({
                "leave_type_id": b.leave_type_id,
                "leave_type": b.leave_type.name,
                "total_days": b.total_days,
                "used_days": b.used_days,
                "remaining_days": b.remaining_days
            })

        emp_dict = emp.to_dict()
        emp_dict["balances"] = balances
        return emp_dict

@app.get("/api/leave-types")
def list_leave_types():
    with get_session() as session:
        types = session.query(LeaveType).all()
        return [t.to_dict() for t in types]

# 2. Leave Requests
@app.get("/api/leave-requests")
def get_leave_requests(status: Optional[str] = None, employee_id: Optional[int] = None):
    with get_session() as session:
        q = session.query(LeaveRequest)
        if status:
            q = q.filter(LeaveRequest.status.ilike(status.strip()))
        if employee_id:
            q = q.filter(LeaveRequest.employee_id == employee_id)
        
        requests = q.order_by(LeaveRequest.applied_at.desc()).all()
        return [r.to_dict() for r in requests]

@app.post("/api/leave-requests")
def apply_leave(data: ApplyLeaveDTO):
    try:
        s_date = datetime.strptime(data.start_date.strip(), "%Y-%m-%d").date()
        e_date = datetime.strptime(data.end_date.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Dates must be in YYYY-MM-DD format")

    if e_date < s_date:
        raise HTTPException(status_code=400, detail="End date cannot be earlier than start date")

    days_requested = (e_date - s_date).days + 1

    with get_session() as session:
        emp = session.query(Employee).filter(Employee.id == data.employee_id).first()
        if not emp:
            raise HTTPException(status_code=404, detail=f"Employee {data.employee_id} not found")

        lt = session.query(LeaveType).filter(LeaveType.name.ilike(data.leave_type_name.strip())).first()
        if not lt:
            raise HTTPException(status_code=404, detail=f"Leave type '{data.leave_type_name}' not found")

        bal = session.query(LeaveBalance).filter(
            LeaveBalance.employee_id == data.employee_id,
            LeaveBalance.leave_type_id == lt.id
        ).first()

        if not bal:
            raise HTTPException(status_code=400, detail="No balance record found for this employee and leave type")

        if bal.remaining_days < days_requested:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance. Requested {days_requested} day(s), but only {bal.remaining_days} remaining."
            )

        req = LeaveRequest(
            employee_id=emp.id,
            leave_type_id=lt.id,
            start_date=s_date,
            end_date=e_date,
            reason=data.reason,
            status="PENDING"
        )
        session.add(req)
        session.flush()
        return req.to_dict()

@app.patch("/api/leave-requests/{request_id}/status")
def update_status(request_id: int, data: UpdateStatusDTO):
    status_upper = data.status.strip().upper()
    if status_upper not in ("APPROVED", "REJECTED"):
        raise HTTPException(status_code=400, detail="Status must be APPROVED or REJECTED")

    with get_session() as session:
        req = session.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
        if not req:
            raise HTTPException(status_code=404, detail="Leave request not found")

        if req.status != "PENDING":
            raise HTTPException(status_code=400, detail=f"Request already processed ({req.status})")

        if status_upper == "APPROVED":
            bal = session.query(LeaveBalance).filter(
                LeaveBalance.employee_id == req.employee_id,
                LeaveBalance.leave_type_id == req.leave_type_id
            ).first()
            if bal:
                bal.used_days = (bal.used_days or 0) + req.days

        req.status = status_upper
        req.decision_notes = data.notes
        return req.to_dict()

# 3. Monthly Analytics & CSV Report
@app.get("/api/reports/monthly")
def get_monthly_report(
    year: int = Query(default=datetime.utcnow().year),
    month: int = Query(default=datetime.utcnow().month),
    download: bool = Query(default=False)
):
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
        status_counts: Dict[str, int] = {"PENDING": 0, "APPROVED": 0, "REJECTED": 0}
        total_days_approved = 0

        rows = []
        for r in requests:
            dept = r.employee.department or "General"
            lt_name = r.leave_type.name
            st = r.status.upper()
            status_counts[st] = status_counts.get(st, 0) + 1

            if st == "APPROVED":
                dept_usage[dept] = dept_usage.get(dept, 0) + r.days
                type_usage[lt_name] = type_usage.get(lt_name, 0) + r.days
                total_days_approved += r.days

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

        if download:
            output = io.StringIO()
            if rows:
                writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            else:
                output.write("Request_ID,Employee_Name,Department,Leave_Type,Start_Date,End_Date,Days,Status,Reason,Decision_Notes\n")
            
            filename = f"leave_report_{year}_{month:02d}.csv"
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        return {
            "year": year,
            "month": month,
            "month_name": calendar.month_name[month],
            "total_requests": len(requests),
            "total_days_approved": total_days_approved,
            "status_counts": status_counts,
            "department_usage": dept_usage,
            "type_usage": type_usage,
            "records": rows
        }
