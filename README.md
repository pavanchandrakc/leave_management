# Leave Management MCP Server

A Model Context Protocol (MCP) server for managing employee leaves, integrated with PostgreSQL (accessible via pgAdmin) and designed to work seamlessly with **Claude Desktop**.

---

## 🌟 Overview

This project implements a Model Context Protocol (MCP) server that empowers Claude Desktop to act as an HR Leave Management Assistant. Using Claude, you can:
- Check employee leave balances.
- Apply for leaves (Casual, Sick, Earned, etc.).
- View, approve, or reject pending leave requests.
- List leave history and upcoming team absences.
- Store and retrieve all records from a **PostgreSQL** database (viewable and manageable in **pgAdmin**).

---

## 🏗️ Architecture

```
+------------------+         stdio         +-------------------------+         SQL          +--------------------+
|  Claude Desktop  | <-------------------> |  Leave Management MCP   | <------------------->  |     PostgreSQL     |
|                  |                       |       (Python/Node)     |                        | (pgAdmin4 manager) |
+------------------+                       +-------------------------+                        +--------------------+
```

---

## 🗄️ Database Setup (PostgreSQL & pgAdmin)

1. Open **pgAdmin** and connect to your PostgreSQL server.
2. Create a new database named `leave_management_db` (or your preferred name).
3. Open the **Query Tool** inside pgAdmin and execute the following DDL script:

```sql
-- 1. Employees Table
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    department VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Leave Types Table
CREATE TABLE leave_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL, -- e.g., 'Sick Leave', 'Casual Leave', 'Paid Leave'
    default_days_allowed INT DEFAULT 12
);

-- 3. Leave Balances Table
CREATE TABLE leave_balances (
    id SERIAL PRIMARY KEY,
    employee_id INT REFERENCES employees(id) ON DELETE CASCADE,
    leave_type_id INT REFERENCES leave_types(id) ON DELETE CASCADE,
    total_days INT NOT NULL,
    used_days INT DEFAULT 0,
    CONSTRAINT unique_employee_leave_type UNIQUE (employee_id, leave_type_id)
);

-- 4. Leave Requests Table
CREATE TABLE leave_requests (
    id SERIAL PRIMARY KEY,
    employee_id INT REFERENCES employees(id) ON DELETE CASCADE,
    leave_type_id INT REFERENCES leave_types(id) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    reason TEXT,
    status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')),
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decision_notes TEXT
);

-- Sample Data Seeding
INSERT INTO leave_types (name, default_days_allowed) VALUES 
('Sick Leave', 10),
('Casual Leave', 12),
('Paid Leave', 15);

INSERT INTO employees (name, email, department) VALUES 
('John Doe', 'john.doe@example.com', 'Engineering'),
('Jane Smith', 'jane.smith@example.com', 'Design');

-- Seed Balances for John Doe (id = 1)
INSERT INTO leave_balances (employee_id, leave_type_id, total_days, used_days) VALUES
(1, 1, 10, 0),
(1, 2, 12, 2),
(1, 3, 15, 0);
```

---

## ⚙️ Environment Configuration

Create a `.env` file in the project root:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=leave_management_db
DB_USER=postgres
DB_PASSWORD=your_postgres_password
```

---

## 🛠️ MCP Tools Exposed to Claude Desktop

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `get_leave_balances` | `employee_id` or `email` | Check remaining & allocated leave days. |
| `apply_leave` | `employee_id`, `leave_type`, `start_date`, `end_date`, `reason` | Submit a new leave request. |
| `list_leave_requests` | `status` *(optional: PENDING, APPROVED, etc.)*, `employee_id` *(optional)* | Retrieve leave requests. |
| `update_leave_status` | `request_id`, `status` *(APPROVED/REJECTED)*, `notes` *(optional)* | Approve or reject a leave request and adjust balance. |
| `get_team_leaves` | `start_date`, `end_date`, `department` *(optional)* | View who is on leave during a given period. |

---

## 🖥️ Claude Desktop Configuration

Add this server to your Claude Desktop configuration file:

- **Windows Path**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS Path**: `~/Library/Application Support/Claude/claude_desktop_config.json`

### Python (`FastMCP` / `mcp`) Setup Example:

```json
{
  "mcpServers": {
    "leave-management": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "d:\\leave_management_mcp",
      "env": {
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "leave_management_db",
        "DB_USER": "postgres",
        "DB_PASSWORD": "your_postgres_password"
      }
    }
  }
}
```

---

## 🚀 Running & Developing

### Prerequisites
- Python 3.10+ (or Node.js 18+)
- PostgreSQL 14+ with pgAdmin 4
- Claude Desktop application

### Setup Instructions
1. Clone / open this repository.
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # On Windows
   ```
3. Install dependencies:
   ```bash
   pip install mcp psycopg2-binary python-dotenv
   ```
4. Configure your `.env` credentials.
5. Restart Claude Desktop.
