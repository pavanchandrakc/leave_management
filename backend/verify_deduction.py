import json
from src.models import get_session, Employee, LeaveType, LeaveBalance, LeaveRequest
from src.api import apply_leave, update_status, ApplyLeaveDTO, UpdateStatusDTO
from src.server import apply_leave as mcp_apply, update_leave_status as mcp_update

def test_api_and_db_flow():
    print("=" * 60)
    print("TEST 1: FastAPI Workflow & PostgreSQL Database Verification")
    print("=" * 60)
    
    with get_session() as s:
        emp = s.query(Employee).filter(Employee.email == "john.doe@example.com").first()
        emp_id = emp.id
        emp_name = emp.name
        casual_type = s.query(LeaveType).filter(LeaveType.name == "Casual Leave").first()
        casual_type_id = casual_type.id
        bal = s.query(LeaveBalance).filter(
            LeaveBalance.employee_id == emp_id,
            LeaveBalance.leave_type_id == casual_type_id
        ).first()
        initial_used = bal.used_days
        initial_remaining = bal.remaining_days
        total_days = bal.total_days
        print(f"Employee: {emp_name} (ID: {emp_id}) | Category: {casual_type.name}")
        print(f"Initial State -> Total: {total_days}, Used: {initial_used}, Remaining: {initial_remaining}")

    # Friday to Monday range:
    # 2026-11-20 (Fri) -> 1 working day
    # 2026-11-21 (Sat) -> Weekend (skipped)
    # 2026-11-22 (Sun) -> Weekend (skipped)
    # 2026-11-23 (Mon) -> 1 working day
    # Total: 2 working days
    dto = ApplyLeaveDTO(
        employee_id=emp_id,
        leave_type_name="Casual Leave",
        start_date="2026-11-20",
        end_date="2026-11-23",
        reason="Testing working days deduction on approval"
    )
    res = apply_leave(dto)
    req_id = res["request_id"]
    working_days = res["days"]
    print(f"\n1. Submitted Request #{req_id}: Status={res['status']}, Deductible Working Days={working_days}")

    # Check DB while PENDING: Balance must NOT change
    with get_session() as s:
        bal = s.query(LeaveBalance).filter(
            LeaveBalance.employee_id == emp_id,
            LeaveBalance.leave_type_id == casual_type_id
        ).first()
        print(f"2. DB check while PENDING -> Used: {bal.used_days}, Remaining: {bal.remaining_days}")
        assert bal.used_days == initial_used, "Balance was prematurely deducted while PENDING!"

    # Approve Request
    up_dto = UpdateStatusDTO(status="APPROVED", notes="Approved during automated test")
    approved_res = update_status(req_id, up_dto)
    print(f"\n3. Approved Request #{req_id}: Status={approved_res['status']}")

    # Check DB after APPROVAL: Balance MUST be updated
    with get_session() as s:
        bal = s.query(LeaveBalance).filter(
            LeaveBalance.employee_id == emp_id,
            LeaveBalance.leave_type_id == casual_type_id
        ).first()
        print(f"4. DB check after APPROVAL -> Used: {bal.used_days}, Remaining: {bal.remaining_days}")
        expected_used = initial_used + working_days
        expected_remaining = initial_remaining - working_days
        assert bal.used_days == expected_used, f"Expected used={expected_used}, got {bal.used_days}"
        assert bal.remaining_days == expected_remaining, f"Expected remaining={expected_remaining}, got {bal.remaining_days}"
        print(">>> CONFIRMED: Working days correctly added to used_days and deducted from remaining_days in DB! <<<")

    # Cancel Request and verify balance restoration
    cancel_dto = UpdateStatusDTO(status="CANCELLED", notes="Cancelled after test")
    update_status(req_id, cancel_dto)
    with get_session() as s:
        bal = s.query(LeaveBalance).filter(
            LeaveBalance.employee_id == emp_id,
            LeaveBalance.leave_type_id == casual_type_id
        ).first()
        print(f"\n5. DB check after CANCELLATION -> Used: {bal.used_days}, Remaining: {bal.remaining_days}")
        assert bal.used_days == initial_used, "Used days not restored after cancellation!"
        print(">>> CONFIRMED: Cancelled request fully restored days back into DB balance! <<<\n")

    # Clean up test request
    with get_session() as s:
        req = s.query(LeaveRequest).filter(LeaveRequest.id == req_id).first()
        if req:
            s.delete(req)
        print("Cleaned up test request.\n")


def test_mcp_flow():
    print("=" * 60)
    print("TEST 2: MCP Server Tools & DB Verification")
    print("=" * 60)
    
    with get_session() as s:
        emp = s.query(Employee).filter(Employee.email == "jane.smith@example.com").first()
        emp_id = emp.id
        emp_name = emp.name
        paid_type = s.query(LeaveType).filter(LeaveType.name == "Paid Leave").first()
        paid_type_id = paid_type.id
        bal = s.query(LeaveBalance).filter(
            LeaveBalance.employee_id == emp_id,
            LeaveBalance.leave_type_id == paid_type_id
        ).first()
        initial_used = bal.used_days
        initial_remaining = bal.remaining_days
        print(f"Employee: {emp_name} (ID: {emp_id}) | Category: {paid_type.name}")
        print(f"Initial State -> Total: {bal.total_days}, Used: {initial_used}, Remaining: {initial_remaining}")

    # Apply via MCP tool: 2026-12-01 (Tue) to 2026-12-03 (Thu) -> 3 working days
    apply_resp = json.loads(mcp_apply(
        employee_id=emp_id,
        leave_type_name="Paid Leave",
        start_date="2026-12-01",
        end_date="2026-12-03",
        reason="MCP verification"
    ))
    req_id = apply_resp["request_id"]
    working_days = apply_resp["working_days"]
    print(f"\n1. MCP Submitted Request #{req_id}: Status={apply_resp['status']}, Working days={working_days}")

    # Approve via MCP tool
    approve_resp = json.loads(mcp_update(request_id=req_id, status="APPROVED", notes="Approved via MCP"))
    print(f"2. MCP Approval response: {approve_resp['message']}")

    # Verify directly from DB
    with get_session() as s:
        bal = s.query(LeaveBalance).filter(
            LeaveBalance.employee_id == emp_id,
            LeaveBalance.leave_type_id == paid_type_id
        ).first()
        print(f"3. DB check after MCP Approval -> Used: {bal.used_days}, Remaining: {bal.remaining_days}")
        expected_used = initial_used + working_days
        expected_remaining = initial_remaining - working_days
        assert bal.used_days == expected_used, f"Expected used={expected_used}, got {bal.used_days}"
        assert bal.remaining_days == expected_remaining, f"Expected remaining={expected_remaining}, got {bal.remaining_days}"
        print(">>> CONFIRMED: MCP tool approval accurately updated the DB balance! <<<")

    # Clean up test request and restore balance
    with get_session() as s:
        bal = s.query(LeaveBalance).filter(
            LeaveBalance.employee_id == emp_id,
            LeaveBalance.leave_type_id == paid_type_id
        ).first()
        bal.used_days = initial_used
        req = s.query(LeaveRequest).filter(LeaveRequest.id == req_id).first()
        if req:
            s.delete(req)
        print("\nCleaned up MCP test request and restored balance.")


if __name__ == "__main__":
    test_api_and_db_flow()
    test_mcp_flow()
