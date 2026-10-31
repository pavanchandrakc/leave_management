-- 1. Employees Table
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    department VARCHAR(50),
    role VARCHAR(20) DEFAULT 'EMPLOYEE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Leave Types Table with Policy Rules
CREATE TABLE IF NOT EXISTS leave_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    default_days_allowed INT DEFAULT 12,
    counts_weekends BOOLEAN DEFAULT FALSE,
    counts_holidays BOOLEAN DEFAULT FALSE,
    max_consecutive_days INT DEFAULT NULL,
    description VARCHAR(255)
);

-- 3. Holidays Table
CREATE TABLE IF NOT EXISTS holidays (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    holiday_date DATE UNIQUE NOT NULL,
    description VARCHAR(255)
);

-- 4. Leave Balances Table
CREATE TABLE IF NOT EXISTS leave_balances (
    id SERIAL PRIMARY KEY,
    employee_id INT REFERENCES employees(id) ON DELETE CASCADE,
    leave_type_id INT REFERENCES leave_types(id) ON DELETE CASCADE,
    total_days INT NOT NULL,
    used_days INT DEFAULT 0,
    CONSTRAINT unique_employee_leave_type UNIQUE (employee_id, leave_type_id)
);

-- 5. Leave Requests Table
CREATE TABLE IF NOT EXISTS leave_requests (
    id SERIAL PRIMARY KEY,
    employee_id INT REFERENCES employees(id) ON DELETE CASCADE,
    leave_type_id INT REFERENCES leave_types(id) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    deductible_days INT DEFAULT NULL,
    reason TEXT,
    status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')),
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decision_notes TEXT
);

-- Sample Data Seeding
INSERT INTO leave_types (name, default_days_allowed, counts_weekends, counts_holidays, max_consecutive_days, description) VALUES 
('Sick Leave', 10, FALSE, FALSE, 15, 'Medical leave for illness and recovery'),
('Casual Leave', 12, FALSE, FALSE, 3, 'Short-term personal time off (max 3 consecutive working days)'),
('Paid Leave', 15, FALSE, FALSE, NULL, 'Earned annual vacation leave')
ON CONFLICT (name) DO UPDATE SET 
    counts_weekends = EXCLUDED.counts_weekends,
    counts_holidays = EXCLUDED.counts_holidays,
    max_consecutive_days = EXCLUDED.max_consecutive_days,
    description = EXCLUDED.description;

INSERT INTO holidays (name, holiday_date, description) VALUES
('New Year''s Day', '2026-01-01', 'National Public Holiday'),
('Republic Day', '2026-01-26', 'National Holiday'),
('Holi', '2026-03-04', 'Festival of Colors'),
('Good Friday', '2026-04-03', 'Public Holiday'),
('Labor Day / May Day', '2026-05-01', 'International Workers'' Day'),
('Independence Day', '2026-08-15', 'National Holiday'),
('Gandhi Jayanti', '2026-10-02', 'National Holiday'),
('Diwali', '2026-11-08', 'Festival of Lights'),
('Christmas Day', '2026-12-25', 'Public Holiday')
ON CONFLICT (holiday_date) DO NOTHING;

INSERT INTO employees (name, email, department, role) VALUES 
('John Doe', 'john.doe@example.com', 'Engineering', 'EMPLOYEE'),
('Jane Smith', 'jane.smith@example.com', 'Design', 'EMPLOYEE'),
('Sarah Connor', 'sarah.hr@example.com', 'Human Resources', 'HR')
ON CONFLICT (email) DO NOTHING;

-- Seed Balances for sample employees
INSERT INTO leave_balances (employee_id, leave_type_id, total_days, used_days)
SELECT e.id, lt.id, lt.default_days_allowed, 0
FROM employees e
CROSS JOIN leave_types lt
ON CONFLICT ON CONSTRAINT unique_employee_leave_type DO NOTHING;
