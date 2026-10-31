-- 1. Employees Table
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    department VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Leave Types Table
CREATE TABLE IF NOT EXISTS leave_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    default_days_allowed INT DEFAULT 12
);

-- 3. Leave Balances Table
CREATE TABLE IF NOT EXISTS leave_balances (
    id SERIAL PRIMARY KEY,
    employee_id INT REFERENCES employees(id) ON DELETE CASCADE,
    leave_type_id INT REFERENCES leave_types(id) ON DELETE CASCADE,
    total_days INT NOT NULL,
    used_days INT DEFAULT 0,
    CONSTRAINT unique_employee_leave_type UNIQUE (employee_id, leave_type_id)
);

-- 4. Leave Requests Table
CREATE TABLE IF NOT EXISTS leave_requests (
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
('Paid Leave', 15)
ON CONFLICT (name) DO NOTHING;

INSERT INTO employees (name, email, department) VALUES 
('John Doe', 'john.doe@example.com', 'Engineering'),
('Jane Smith', 'jane.smith@example.com', 'Design')
ON CONFLICT (email) DO NOTHING;

-- Seed Balances for sample employees
INSERT INTO leave_balances (employee_id, leave_type_id, total_days, used_days)
SELECT e.id, lt.id, lt.default_days_allowed, 0
FROM employees e
CROSS JOIN leave_types lt
ON CONFLICT ON CONSTRAINT unique_employee_leave_type DO NOTHING;
