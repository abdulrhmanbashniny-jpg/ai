-- db/init_supabase.sql
-- SQL schema for HR CRM (Postgres / Supabase)

-- Table: employees
CREATE TABLE IF NOT EXISTS employees (
  emp_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  dept TEXT,
  role TEXT NOT NULL,
  password TEXT,
  hire_date DATE,
  contract_type TEXT,
  leave_balances JSONB DEFAULT '{}'::jsonb,
  manager_id TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Table: requests (generalized requests for leave, loan, purchase, complaint, etc.)
CREATE TABLE IF NOT EXISTS requests (
  id BIGSERIAL PRIMARY KEY,
  emp_id TEXT NOT NULL REFERENCES employees(emp_id) ON DELETE SET NULL,
  emp_name TEXT,
  dept TEXT,
  service_type TEXT NOT NULL,
  sub_type TEXT,
  details TEXT,
  start_date DATE,
  end_date DATE,
  days INTEGER,
  substitute_id TEXT,
  substitute_name TEXT,
  status_substitute TEXT DEFAULT 'Not Required',
  status_manager TEXT DEFAULT 'Pending',
  status_hr TEXT DEFAULT 'Pending',
  substitute_note TEXT,
  manager_note TEXT,
  hr_note TEXT,
  substitute_action_at TIMESTAMPTZ,
  manager_action_at TIMESTAMPTZ,
  hr_action_at TIMESTAMPTZ,
  final_status TEXT DEFAULT 'Pending',
  phone TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Table: audit_logs
CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGSERIAL PRIMARY KEY,
  actor_emp_id TEXT,
  actor_name TEXT,
  action TEXT,
  target_request_id BIGINT,
  note TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Table: ai_analyses
CREATE TABLE IF NOT EXISTS ai_analyses (
  id BIGSERIAL PRIMARY KEY,
  request_id BIGINT REFERENCES requests(id) ON DELETE CASCADE,
  summary TEXT,
  score NUMERIC,
  details JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Table: attendance (basic)
CREATE TABLE IF NOT EXISTS attendance (
  id BIGSERIAL PRIMARY KEY,
  emp_id TEXT REFERENCES employees(emp_id),
  check_in TIMESTAMPTZ,
  check_out TIMESTAMPTZ,
  source TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Table: payroll
CREATE TABLE IF NOT EXISTS payroll (
  id BIGSERIAL PRIMARY KEY,
  emp_id TEXT REFERENCES employees(emp_id),
  period_start DATE,
  period_end DATE,
  gross NUMERIC,
  allowances JSONB,
  deductions JSONB,
  net NUMERIC,
  status TEXT DEFAULT 'Draft',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Table: contracts
CREATE TABLE IF NOT EXISTS contracts (
  id BIGSERIAL PRIMARY KEY,
  emp_id TEXT REFERENCES employees(emp_id),
  contract_type TEXT,
  start_date DATE,
  end_date DATE,
  doc_url TEXT,
  status TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Table: candidates
CREATE TABLE IF NOT EXISTS candidates (
  id BIGSERIAL PRIMARY KEY,
  name TEXT,
  email TEXT,
  phone TEXT,
  applied_for TEXT,
  resume_url TEXT,
  status TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Table: trainings
CREATE TABLE IF NOT EXISTS trainings (
  id BIGSERIAL PRIMARY KEY,
  title TEXT,
  description TEXT,
  start_date DATE,
  end_date DATE,
  participants JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Table: complaints
CREATE TABLE IF NOT EXISTS complaints (
  id BIGSERIAL PRIMARY KEY,
  emp_id TEXT REFERENCES employees(emp_id),
  title TEXT,
  description TEXT,
  status TEXT DEFAULT 'Open',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Table: documents
CREATE TABLE IF NOT EXISTS documents (
  id BIGSERIAL PRIMARY KEY,
  owner_emp_id TEXT REFERENCES employees(emp_id),
  title TEXT,
  doc_url TEXT,
  tags TEXT[],
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Table: permissions (optional - for dynamic RBAC)
CREATE TABLE IF NOT EXISTS permissions (
  id BIGSERIAL PRIMARY KEY,
  role_name TEXT UNIQUE,
  permissions JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_requests_emp_id ON requests(emp_id);
CREATE INDEX IF NOT EXISTS idx_requests_dept ON requests(dept);
CREATE INDEX IF NOT EXISTS idx_ai_request_id ON ai_analyses(request_id);