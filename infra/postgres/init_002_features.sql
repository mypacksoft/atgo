-- ATGO 002 — feature additions
-- Adds: employee accounts, correction/leave requests, notifications,
-- DNS automation tables, security/abuse tables, on-premise license tables.
-- Idempotent: every CREATE uses IF NOT EXISTS.

-- ============================================================
-- EMPLOYEE SELF-SERVICE ACCOUNTS
-- ============================================================
-- Distinct from `users` (HR/admin). Employees authenticate with their
-- corporate email + password OR a magic-link/code from HR. Each row maps
-- 1:1 to an `employees` row.

CREATE TABLE IF NOT EXISTS employee_accounts (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    employee_id     BIGINT NOT NULL UNIQUE REFERENCES employees(id) ON DELETE CASCADE,
    email           CITEXT,
    password_hash   TEXT,
    locale          VARCHAR(10) DEFAULT 'en',
    last_login_at   TIMESTAMPTZ,
    invite_token    TEXT,
    invite_expires_at TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_emp_acc_tenant ON employee_accounts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_emp_acc_email ON employee_accounts(email) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uniq_emp_acc_email_tenant
    ON employee_accounts(tenant_id, email) WHERE email IS NOT NULL;

CREATE TABLE IF NOT EXISTS employee_sessions (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    account_id      BIGINT NOT NULL REFERENCES employee_accounts(id) ON DELETE CASCADE,
    refresh_token_hash TEXT NOT NULL UNIQUE,
    user_agent      TEXT,
    ip_address      INET,
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_emp_sess_account ON employee_sessions(account_id);

-- ============================================================
-- CORRECTION + LEAVE REQUESTS
-- ============================================================

CREATE TABLE IF NOT EXISTS attendance_correction_requests (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    employee_id     BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    work_date       DATE NOT NULL,
    requested_check_in  TIMESTAMPTZ,
    requested_check_out TIMESTAMPTZ,
    reason          TEXT NOT NULL,
    attachment_url  TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending|approved|rejected|cancelled
    reviewed_by     BIGINT REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at     TIMESTAMPTZ,
    review_notes    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_correction_status ON attendance_correction_requests(tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_correction_employee ON attendance_correction_requests(employee_id, work_date DESC);

CREATE TABLE IF NOT EXISTS leave_requests (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    employee_id     BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    leave_type      TEXT NOT NULL,            -- annual|sick|unpaid|other
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    half_day        BOOLEAN NOT NULL DEFAULT FALSE,
    reason          TEXT,
    attachment_url  TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    reviewed_by     BIGINT REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at     TIMESTAMPTZ,
    review_notes    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (start_date <= end_date)
);
CREATE INDEX IF NOT EXISTS idx_leave_status ON leave_requests(tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leave_employee ON leave_requests(employee_id, start_date DESC);

-- ============================================================
-- NOTIFICATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS notifications (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    audience        TEXT NOT NULL,            -- user|employee_account
    audience_id     BIGINT NOT NULL,
    kind            TEXT NOT NULL,            -- correction_approved|device_offline|...
    title           TEXT NOT NULL,
    body            TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_notif_audience
    ON notifications(audience, audience_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notif_unread
    ON notifications(audience, audience_id) WHERE read_at IS NULL;

-- ============================================================
-- DNS PROVIDER (Cloudflare auto-DNS) + verification log
-- ============================================================

CREATE TABLE IF NOT EXISTS dns_provider_accounts (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    provider            TEXT NOT NULL,        -- 'cloudflare'
    encrypted_api_token TEXT NOT NULL,
    account_id          TEXT,
    status              TEXT NOT NULL DEFAULT 'active',
    last_used_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, provider)
);
CREATE INDEX IF NOT EXISTS idx_dns_provider_tenant ON dns_provider_accounts(tenant_id);

CREATE TABLE IF NOT EXISTS dns_verification_attempts (
    id                BIGSERIAL PRIMARY KEY,
    tenant_id         BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    tenant_domain_id  BIGINT NOT NULL REFERENCES tenant_domains(id) ON DELETE CASCADE,
    check_type        TEXT NOT NULL,        -- 'cname'|'txt'
    expected_value    TEXT NOT NULL,
    actual_value      TEXT,
    success           BOOLEAN NOT NULL,
    error_message     TEXT,
    checked_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dns_attempt_domain
    ON dns_verification_attempts(tenant_domain_id, checked_at DESC);

CREATE TABLE IF NOT EXISTS domain_disputes (
    id                BIGSERIAL PRIMARY KEY,
    normalized_domain TEXT NOT NULL,
    claimed_by_tenant BIGINT REFERENCES tenants(id) ON DELETE SET NULL,
    requesting_email  TEXT NOT NULL,
    evidence          TEXT,
    status            TEXT NOT NULL DEFAULT 'open',  -- open|resolved|rejected
    resolved_by       BIGINT REFERENCES users(id) ON DELETE SET NULL,
    resolved_at       TIMESTAMPTZ,
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_domain_disputes_open ON domain_disputes(status, created_at DESC);

-- ============================================================
-- SECURITY / ABUSE / RATE LIMIT LOG
-- ============================================================

CREATE TABLE IF NOT EXISTS security_events (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT REFERENCES tenants(id) ON DELETE SET NULL,
    kind            TEXT NOT NULL,           -- failed_login|abuse|admin_action|...
    severity        TEXT NOT NULL DEFAULT 'info', -- info|warn|alert|critical
    message         TEXT,
    ip_address      INET,
    user_agent      TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sec_events_tenant
    ON security_events(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sec_events_kind
    ON security_events(kind, created_at DESC);

CREATE TABLE IF NOT EXISTS blocked_ips (
    ip_address      INET PRIMARY KEY,
    reason          TEXT NOT NULL,
    blocked_until   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- LICENSE KEYS (on-premise)
-- ============================================================

CREATE TABLE IF NOT EXISTS license_keys (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT REFERENCES tenants(id) ON DELETE SET NULL,
    customer_email  CITEXT NOT NULL,
    license_key     TEXT NOT NULL UNIQUE,
    plan_id         TEXT NOT NULL REFERENCES plans(id),
    device_limit    INT,
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS onpremise_instances (
    id              BIGSERIAL PRIMARY KEY,
    license_key_id  BIGINT NOT NULL REFERENCES license_keys(id) ON DELETE CASCADE,
    machine_fingerprint TEXT,
    public_ip       INET,
    version         TEXT,
    last_check_at   TIMESTAMPTZ,
    last_status     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_onpremise_lic ON onpremise_instances(license_key_id);

-- ============================================================
-- HELPERS for partition rotation
-- ============================================================
-- Convenience function — create the next monthly partition for both
-- raw_attendance_logs and normalized_attendance_logs. Call from a cron.

CREATE OR REPLACE FUNCTION ensure_attendance_partition(target DATE)
RETURNS void AS $$
DECLARE
    y INT := EXTRACT(YEAR FROM target);
    m INT := EXTRACT(MONTH FROM target);
    p_start DATE := make_date(y, m, 1);
    p_end   DATE := (p_start + INTERVAL '1 month')::DATE;
    raw_name  TEXT := format('raw_attendance_logs_y%sm%s', y, lpad(m::text, 2, '0'));
    norm_name TEXT := format('normalized_attendance_logs_y%sm%s', y, lpad(m::text, 2, '0'));
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF raw_attendance_logs FOR VALUES FROM (%L) TO (%L)',
        raw_name, p_start, p_end
    );
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF normalized_attendance_logs FOR VALUES FROM (%L) TO (%L)',
        norm_name, p_start, p_end
    );
END $$ LANGUAGE plpgsql;

-- Pre-create 12 months of partitions starting from current month, so that
-- the system never gets stuck waiting on a worker.
DO $$
DECLARE
    i INT;
    d DATE := date_trunc('month', NOW())::DATE;
BEGIN
    FOR i IN 0..12 LOOP
        PERFORM ensure_attendance_partition((d + (i || ' months')::INTERVAL)::DATE);
    END LOOP;
END $$;

-- ============================================================
-- RLS for the new tenant-scoped tables
-- ============================================================
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'employee_accounts','employee_sessions',
        'attendance_correction_requests','leave_requests',
        'notifications','dns_provider_accounts','dns_verification_attempts'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format($f$
            DROP POLICY IF EXISTS tenant_iso ON %I;
            CREATE POLICY tenant_iso ON %I
                USING (tenant_id = current_tenant_id() OR is_admin_bypass())
                WITH CHECK (tenant_id = current_tenant_id() OR is_admin_bypass())
        $f$, t, t);
    END LOOP;
END $$;
