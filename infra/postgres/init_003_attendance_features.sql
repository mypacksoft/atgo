-- ATGO 003 — attendance features
-- Adds: auto-created employees, holidays, shifts, employee positions,
-- mirrors of common Vietnamese HRM tables (LST_BoPhan, HRM_HoSo,
-- AttendLogMachine, AttendLog_CurrentAvailable).
-- Idempotent.

-- ============================================================
-- Employees: auto-create + source tracking
-- ============================================================

ALTER TABLE employees ADD COLUMN IF NOT EXISTS auto_created BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE employees ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'manual';
        -- 'manual' | 'machine' | 'odoo' | 'import'

ALTER TABLE employees ADD COLUMN IF NOT EXISTS gender VARCHAR(10);
ALTER TABLE employees ADD COLUMN IF NOT EXISTS dob DATE;
ALTER TABLE employees ADD COLUMN IF NOT EXISTS national_id TEXT;
ALTER TABLE employees ADD COLUMN IF NOT EXISTS address TEXT;
ALTER TABLE employees ADD COLUMN IF NOT EXISTS photo_url TEXT;
ALTER TABLE employees ADD COLUMN IF NOT EXISTS position_title TEXT;
ALTER TABLE employees ADD COLUMN IF NOT EXISTS default_shift_code TEXT;
ALTER TABLE employees ADD COLUMN IF NOT EXISTS odoo_id INT;
        -- mirror of hr.employee.id when synced from Odoo

CREATE INDEX IF NOT EXISTS idx_employees_odoo
    ON employees(tenant_id, odoo_id) WHERE odoo_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_employees_auto_created
    ON employees(tenant_id, auto_created, created_at DESC) WHERE auto_created;

-- ============================================================
-- Tenant settings: auto-sync toggles
-- ============================================================

ALTER TABLE tenants ADD COLUMN IF NOT EXISTS auto_create_from_machine BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS auto_create_from_odoo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS work_week_days SMALLINT NOT NULL DEFAULT 6;
        -- 5=Mon-Fri, 6=Mon-Sat, 7=Mon-Sun
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS standard_shift_minutes INT NOT NULL DEFAULT 480;
        -- 480 minutes = 8 hours

-- ============================================================
-- Shifts (Ca làm việc — equivalent of Phuc Hao "Ca")
-- ============================================================

CREATE TABLE IF NOT EXISTS shifts (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code            TEXT NOT NULL,
    name            TEXT NOT NULL,
    start_time      TIME NOT NULL,                 -- e.g. '08:00'
    end_time        TIME NOT NULL,                 -- e.g. '17:00'
    break_minutes   INT NOT NULL DEFAULT 60,
    crosses_midnight BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, code)
);
CREATE INDEX IF NOT EXISTS idx_shifts_tenant ON shifts(tenant_id);

-- ============================================================
-- Holidays (Ngày nghỉ lễ)
-- ============================================================

CREATE TABLE IF NOT EXISTS holidays (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    holiday_date DATE NOT NULL,
    name        TEXT NOT NULL,
    is_paid     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, holiday_date)
);
CREATE INDEX IF NOT EXISTS idx_holidays_tenant_date ON holidays(tenant_id, holiday_date);

-- ============================================================
-- Daily attendance summary (one row per employee per day)
-- Equivalent of Phuc Hao "Bảng chấm công" cell
-- Status code mirrors Odoo dashboard: P, A, L, H, W
-- ============================================================

CREATE TABLE IF NOT EXISTS attendance_daily (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    employee_id     BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    work_date       DATE NOT NULL,
    status_code     CHAR(1) NOT NULL,
        -- 'P' present, 'A' absent, 'L' on leave, 'H' holiday, 'W' weekend, '-' not enrolled
    punch_count     SMALLINT NOT NULL DEFAULT 0,
    first_in        TIMESTAMPTZ,
    last_out        TIMESTAMPTZ,
    worked_minutes  INT,
    overtime_minutes INT NOT NULL DEFAULT 0,
    late_minutes    INT NOT NULL DEFAULT 0,
    early_leave_minutes INT NOT NULL DEFAULT 0,
    leave_request_id BIGINT,    -- nullable: link to leave_requests when status_code='L'
    notes           TEXT,
    is_manually_edited BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (employee_id, work_date)
);
CREATE INDEX IF NOT EXISTS idx_att_daily_tenant_date
    ON attendance_daily(tenant_id, work_date DESC);
CREATE INDEX IF NOT EXISTS idx_att_daily_emp_month
    ON attendance_daily(employee_id, work_date);

-- ============================================================
-- Employee currently clocked-in view (Nhân viên hiện diện)
-- Maintained by ADMS receiver: insert on check_in, delete on check_out.
-- ============================================================

CREATE TABLE IF NOT EXISTS employee_presence (
    tenant_id        BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    employee_id      BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    device_id        BIGINT REFERENCES devices(id) ON DELETE SET NULL,
    last_in_at       TIMESTAMPTZ NOT NULL,
    expected_out_at  TIMESTAMPTZ,
    PRIMARY KEY (tenant_id, employee_id)
);
CREATE INDEX IF NOT EXISTS idx_presence_tenant ON employee_presence(tenant_id, last_in_at DESC);

-- ============================================================
-- RLS for new tables
-- ============================================================

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'shifts','holidays','attendance_daily','employee_presence'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format($f$
            CREATE POLICY tenant_iso ON %I
                USING (tenant_id = current_tenant_id() OR is_admin_bypass())
                WITH CHECK (tenant_id = current_tenant_id() OR is_admin_bypass())
        $f$, t);
    END LOOP;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
