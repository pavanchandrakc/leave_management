# LeaveFlow HR - Leave Management System & MCP Server

A comprehensive Employee Leave Management System integrated with **PostgreSQL (pgAdmin)**, a **FastAPI backend**, a modern **Responsive Web UI**, and **Claude Desktop MCP integration**.

---

## 📁 Project Structure

```
d:\leave_management_mcp\
├── backend\
│   ├── .env                       # PostgreSQL credentials
│   ├── migrate.py                 # Schema migration helper
│   ├── requirements.txt           # Python dependencies
│   ├── run_api.py                 # FastAPI backend server (Port 8000)
│   ├── run_mcp.py                 # Claude Desktop MCP stdio server
│   ├── schema.sql                 # Base SQL schema
│   └── src\
│       ├── api.py                 # REST API endpoints + CSV export
│       ├── db.py                  # Database connection helpers
│       ├── models.py              # SQLAlchemy 2.0 ORM models
│       └── server.py              # FastMCP tools
├── frontend\
│   ├── index.html                 # Main Single Page App
│   ├── style.css                  # Dark glassmorphic design system
│   └── app.js                     # Frontend logic (Roles, Forms, CSV)
└── .venv\                         # Python virtual environment
```

---

## 🚀 Running the System

### 1. Start the Backend API
```powershell
.venv\Scripts\python backend\run_api.py
```
- API runs at: `http://127.0.0.1:8000`
- Interactive Swagger docs at: `http://127.0.0.1:8000/docs`

### 2. Start the Frontend Web UI
```powershell
.venv\Scripts\python -m http.server 5173 --directory frontend
```
- Open your browser to: **`http://localhost:5173`**

---

## 🌟 Key Features

### 👤 1. Employee Portal
- **Profile Selector**: Switch between employees (e.g. John Doe, Jane Smith).
- **Live KPI Balance Cards**: Shows Sick Leave, Casual Leave, and Paid Leave balances.
- **Request Leave Form**: Auto-calculates days, verifies available balance, and submits requests.
- **My Leave History**: Real-time status tracker (Pending, Approved, Rejected).

### 🛡️ 2. HR Admin Portal
- Switch user to **Sarah Connor (HR)** to activate the HR Admin View.
- **Pending Approvals Queue**: Live table of all pending submissions from employees.
- **1-Click Approve / Reject**: With optional notes.
- **Automatic Balance Deduction**: Approving a request instantly decreases the employee's available days in PostgreSQL.

### 📊 3. Monthly Analytics & CSV Export
- Filter by any **Month & Year** (e.g., October 2026, November 2026).
- **KPI Metrics**: Total applications, total absent days, pending count.
- **Department Breakdown**: Absenteeism distribution by department (Engineering, Design, HR).
- **Export CSV**: One-click download of the complete monthly report as a `.csv` file.

---

## 🤖 Claude Desktop Configuration

The MCP server has been updated to point to the new `backend/run_mcp.py` runner:

```json
{
  "mcpServers": {
    "leave-management": {
      "command": "D:\\leave_management_mcp\\.venv\\Scripts\\python.exe",
      "args": ["D:\\leave_management_mcp\\backend\\run_mcp.py"],
      "cwd": "D:\\leave_management_mcp\\backend",
      "env": {
        "PYTHONPATH": "D:\\leave_management_mcp\\backend"
      }
    }
  }
}
```

### Available Claude Tools:
- `get_leave_balances(employee_id, email)`
- `apply_leave(employee_id, leave_type_name, start_date, end_date, reason)`
- `list_leave_requests(status, employee_id)`
- `update_leave_status(request_id, status, notes)`
- `get_team_leaves(start_date, end_date, department)`
- `generate_monthly_leave_report(year, month, format='json'|'csv')`
