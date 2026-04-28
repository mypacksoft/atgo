-- ATGO initial schema
-- Single domain: atgo.io · Tenant isolation via Postgres RLS

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

-- ============================================================
-- USERS, PLANS, TENANTS
-- ============================================================

CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           CITEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       TEXT,
    locale          VARCHAR(10) DEFAULT 'en',
    timezone        VARCHAR(64) DEFAULT 'UTC',
    is_super_admin  BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE plans (
    id                       TEXT PRIMARY KEY,
    name                     TEXT NOT NULL,
    monthly_price_usd_cents  INT NOT NULL DEFAULT 0,
    device_limit             INT,
    employee_limit           INT,
    log_retention_days       INT NOT NULL DEFAULT 30,
    monthly_log_quota        INT,
    allow_custom_domain      BOOLEAN NOT NULL DEFAULT FALSE,
    custom_domain_limit      INT NOT NULL DEFAULT 0,
    allow_auto_dns           BOOLEAN NOT NULL DEFAULT FALSE,
    allow_advanced_rules     BOOLEAN NOT NULL DEFAULT FALSE,
    sync_interval_seconds    INT NOT NULL DEFAULT 60,
    is_public                BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order               INT NOT NULL DEFAULT 0
);

CREATE TABLE tenants (
    id                BIGSERIAL PRIMARY KEY,
    slug              TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    plan_id           TEXT NOT NULL REFERENCES plans(id) DEFAULT 'free',
    billing_country   CHAR(2),
    default_timezone  VARCHAR(64) DEFAULT 'UTC',
    default_locale    VARCHAR(10) DEFAULT 'en',
    primary_domain    TEXT,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    suspended_at      TIMESTAMPTZ,
    suspension_reason TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT slug_format CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,28}[a-z0-9]$')
);
CREATE INDEX idx_tenants_slug ON tenants(slug);

CREATE TABLE tenant_members (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, user_id)
);
CREATE INDEX idx_tenant_members_user ON tenant_members(user_id);

-- ============================================================
-- DOMAINS
-- ============================================================

CREATE TABLE tenant_domains (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    domain              TEXT NOT NULL,
    normalized_domain   TEXT NOT NULL,
    domain_type         TEXT NOT NULL,
    status              TEXT NOT NULL,
    is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
    verification_token  TEXT,
    cname_target        TEXT,
    txt_record_name     TEXT,
    txt_record_value    TEXT,
    ssl_status          TEXT NOT NULL DEFAULT 'pending',
    provider            TEXT,
    cloudflare_zone_id  TEXT,
    expires_at          TIMESTAMPTZ,
    verified_at         TIMESTAMPTZ,
    last_checked_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX uniq_active_domain
    ON tenant_domains (normalized_domain)
    WHERE status IN ('pending', 'verified', 'active', 'restricted');
CREATE INDEX idx_tenant_domains_tenant ON tenant_domains(tenant_id);

-- ============================================================
-- BRANCHES & DEPARTMENTS
-- ============================================================

CREATE TABLE branches (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code        TEXT NOT NULL,
    name        TEXT NOT NULL,
    timezone    VARCHAR(64),
    address     TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, code)
);

CREATE TABLE departments (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code        TEXT NOT NULL,
    name        TEXT NOT NULL,
    parent_id   BIGINT REFERENCES departments(id) ON DELETE SET NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, code)
);

-- ============================================================
-- DEVICES
-- ============================================================

CREATE TABLE devices (
    id                       BIGSERIAL PRIMARY KEY,
    tenant_id                BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    branch_id                BIGINT REFERENCES branches(id) ON DELETE SET NULL,
    serial_number            TEXT NOT NULL,
    device_code              TEXT NOT NULL,
    name                     TEXT NOT NULL,
    model                    TEXT,
    firmware_version         TEXT,
    timezone                 VARCHAR(64),
    secret_hash              TEXT,
    capabilities             JSONB DEFAULT '{}'::jsonb,
    status                   TEXT NOT NULL DEFAULT 'pending_claim',
    last_seen_at             TIMESTAMPTZ,
    last_ip                  INET,
    is_online                BOOLEAN NOT NULL DEFAULT FALSE,
    pending_commands_count   INT NOT NULL DEFAULT 0,
    last_attlog_stamp        TEXT,
    last_operlog_stamp       TEXT,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX uniq_devices_active_sn
    ON devices(serial_number)
    WHERE status IN ('pending_claim', 'active');
CREATE UNIQUE INDEX uniq_devices_code ON devices(device_code);
CREATE INDEX idx_devices_tenant ON devices(tenant_id);

CREATE TABLE device_claim_codes (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    device_id   BIGINT REFERENCES devices(id) ON DELETE CASCADE,
    code        TEXT NOT NULL UNIQUE,
    bound_serial TEXT,
    claimed_at  TIMESTAMPTZ,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_claim_codes_tenant ON device_claim_codes(tenant_id);
CREATE INDEX idx_claim_codes_active ON device_claim_codes(code) WHERE claimed_at IS NULL;

CREATE TABLE device_commands (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    device_id       BIGINT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    command_type    TEXT NOT NULL,
    raw_command     TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    status          TEXT NOT NULL DEFAULT 'pending',
    attempt_count   INT NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    delivered_at    TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,
    return_code     INT,
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_dev_cmd_pending ON device_commands(device_id, status, expires_at) WHERE status = 'pending';

-- ============================================================
-- EMPLOYEES
-- ============================================================

CREATE TABLE employees (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    branch_id       BIGINT REFERENCES branches(id) ON DELETE SET NULL,
    department_id   BIGINT REFERENCES departments(id) ON DELETE SET NULL,
    employee_code   TEXT NOT NULL,
    device_pin      TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    card_number     TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    hired_at        DATE,
    terminated_at   DATE,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, device_pin),
    UNIQUE (tenant_id, employee_code)
);
CREATE INDEX idx_employees_tenant ON employees(tenant_id);

CREATE TABLE employee_device_assignments (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    employee_id     BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    device_id       BIGINT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    sync_status     TEXT NOT NULL DEFAULT 'pending',
    last_synced_at  TIMESTAMPTZ,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (employee_id, device_id)
);
CREATE INDEX idx_eda_tenant ON employee_device_assignments(tenant_id);

-- ============================================================
-- ATTENDANCE LOGS (partitioned monthly by received_at / punched_at)
-- ============================================================

CREATE TABLE raw_attendance_logs (
    id              BIGSERIAL,
    tenant_id       BIGINT NOT NULL,
    device_id       BIGINT,
    serial_number   TEXT NOT NULL,
    payload_table   TEXT,
    raw_payload     TEXT NOT NULL,
    source_ip       INET,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, received_at)
) PARTITION BY RANGE (received_at);

CREATE TABLE raw_attendance_logs_default PARTITION OF raw_attendance_logs DEFAULT;
CREATE TABLE raw_attendance_logs_y2026m04 PARTITION OF raw_attendance_logs FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE raw_attendance_logs_y2026m05 PARTITION OF raw_attendance_logs FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE raw_attendance_logs_y2026m06 PARTITION OF raw_attendance_logs FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE raw_attendance_logs_y2026m07 PARTITION OF raw_attendance_logs FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE INDEX idx_raw_logs_tenant ON raw_attendance_logs (tenant_id, received_at DESC);
CREATE INDEX idx_raw_logs_sn ON raw_attendance_logs (serial_number, received_at DESC);

CREATE TABLE normalized_attendance_logs (
    id                BIGSERIAL,
    tenant_id         BIGINT NOT NULL,
    device_id         BIGINT NOT NULL,
    employee_id       BIGINT,
    device_pin        TEXT NOT NULL,
    punched_at        TIMESTAMPTZ NOT NULL,
    punch_state       SMALLINT,
    verify_type       SMALLINT,
    work_code         TEXT,
    idempotency_key   TEXT NOT NULL,
    raw_log_id        BIGINT,
    odoo_synced_at    TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, punched_at)
) PARTITION BY RANGE (punched_at);

CREATE TABLE normalized_attendance_logs_default PARTITION OF normalized_attendance_logs DEFAULT;
CREATE TABLE normalized_attendance_logs_y2026m04 PARTITION OF normalized_attendance_logs FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE normalized_attendance_logs_y2026m05 PARTITION OF normalized_attendance_logs FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE normalized_attendance_logs_y2026m06 PARTITION OF normalized_attendance_logs FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE normalized_attendance_logs_y2026m07 PARTITION OF normalized_attendance_logs FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE UNIQUE INDEX uniq_norm_idem ON normalized_attendance_logs (idempotency_key, punched_at);
CREATE INDEX idx_norm_tenant_date ON normalized_attendance_logs (tenant_id, punched_at DESC);
CREATE INDEX idx_norm_employee_date ON normalized_attendance_logs (employee_id, punched_at DESC);
CREATE INDEX idx_norm_unsynced_odoo ON normalized_attendance_logs (tenant_id, punched_at) WHERE odoo_synced_at IS NULL;

CREATE TABLE attendance_records (
    id                BIGSERIAL PRIMARY KEY,
    tenant_id         BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    employee_id       BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    work_date         DATE NOT NULL,
    first_check_in    TIMESTAMPTZ,
    last_check_out    TIMESTAMPTZ,
    total_punches     INT NOT NULL DEFAULT 0,
    worked_minutes    INT,
    status            TEXT,
    is_late           BOOLEAN DEFAULT FALSE,
    is_early_leave    BOOLEAN DEFAULT FALSE,
    notes             TEXT,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (employee_id, work_date)
);
CREATE INDEX idx_att_records_tenant_date ON attendance_records(tenant_id, work_date DESC);

-- ============================================================
-- API KEYS, BILLING, USAGE, AUDIT
-- ============================================================

CREATE TABLE api_keys (
    id           BIGSERIAL PRIMARY KEY,
    tenant_id    BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id      BIGINT REFERENCES users(id) ON DELETE SET NULL,
    name         TEXT NOT NULL,
    prefix       TEXT NOT NULL,
    key_hash     TEXT NOT NULL UNIQUE,
    scopes       TEXT[] NOT NULL DEFAULT '{}',
    last_used_at TIMESTAMPTZ,
    expires_at   TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id);

CREATE TABLE subscriptions (
    id                          BIGSERIAL PRIMARY KEY,
    tenant_id                   BIGINT NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
    plan_id                     TEXT NOT NULL REFERENCES plans(id),
    status                      TEXT NOT NULL,
    payment_provider            TEXT,
    provider_subscription_id    TEXT,
    provider_customer_id        TEXT,
    currency                    CHAR(3),
    amount_local                BIGINT,
    amount_usd_cents            INT,
    billing_country             CHAR(2),
    extra_devices_count         INT NOT NULL DEFAULT 0,
    current_period_start        TIMESTAMPTZ,
    current_period_end          TIMESTAMPTZ,
    cancel_at_period_end        BOOLEAN NOT NULL DEFAULT FALSE,
    cancelled_at                TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE billing_events (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           BIGINT REFERENCES tenants(id) ON DELETE SET NULL,
    provider            TEXT NOT NULL,
    event_type          TEXT NOT NULL,
    raw_payload         JSONB NOT NULL,
    signature_verified  BOOLEAN NOT NULL,
    processed_at        TIMESTAMPTZ,
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_billing_events_unprocessed ON billing_events(provider, created_at) WHERE processed_at IS NULL;

CREATE TABLE plan_usage (
    tenant_id            BIGINT PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    period_start         DATE NOT NULL,
    period_end           DATE NOT NULL,
    log_count            INT NOT NULL DEFAULT 0,
    device_count         INT NOT NULL DEFAULT 0,
    employee_count       INT NOT NULL DEFAULT 0,
    custom_domain_count  INT NOT NULL DEFAULT 0,
    storage_bytes        BIGINT NOT NULL DEFAULT 0,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT REFERENCES tenants(id) ON DELETE CASCADE,
    actor_user_id   BIGINT REFERENCES users(id) ON DELETE SET NULL,
    actor_type      TEXT NOT NULL,
    action          TEXT NOT NULL,
    resource_type   TEXT,
    resource_id     TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_tenant ON audit_logs(tenant_id, created_at DESC);

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================

CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS BIGINT AS $$
DECLARE tid TEXT;
BEGIN
    BEGIN tid := current_setting('app.tenant_id', TRUE);
    EXCEPTION WHEN OTHERS THEN RETURN NULL;
    END;
    IF tid IS NULL OR tid = '' THEN RETURN NULL; END IF;
    RETURN tid::BIGINT;
END $$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION is_admin_bypass() RETURNS BOOLEAN AS $$
BEGIN
    RETURN current_setting('app.bypass_rls', TRUE) = '1';
EXCEPTION WHEN OTHERS THEN RETURN FALSE;
END $$ LANGUAGE plpgsql STABLE;

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'tenants','tenant_members','tenant_domains',
        'branches','departments',
        'devices','device_claim_codes','device_commands',
        'employees','employee_device_assignments',
        'attendance_records','api_keys','subscriptions','plan_usage','audit_logs',
        'raw_attendance_logs','normalized_attendance_logs'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    END LOOP;
END $$;

CREATE POLICY tenant_self ON tenants
    USING (id = current_tenant_id() OR is_admin_bypass())
    WITH CHECK (id = current_tenant_id() OR is_admin_bypass());

CREATE POLICY tm_iso ON tenant_members
    USING (tenant_id = current_tenant_id() OR is_admin_bypass())
    WITH CHECK (tenant_id = current_tenant_id() OR is_admin_bypass());

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'tenant_domains','branches','departments',
        'devices','device_claim_codes','device_commands',
        'employees','employee_device_assignments',
        'attendance_records','api_keys','subscriptions','plan_usage','audit_logs',
        'raw_attendance_logs','normalized_attendance_logs'
    ] LOOP
        EXECUTE format($f$
            CREATE POLICY tenant_iso ON %I
                USING (tenant_id = current_tenant_id() OR is_admin_bypass())
                WITH CHECK (tenant_id = current_tenant_id() OR is_admin_bypass())
        $f$, t);
    END LOOP;
END $$;

-- ============================================================
-- SEED PLANS
-- ============================================================

INSERT INTO plans
    (id, name, monthly_price_usd_cents, device_limit, employee_limit, log_retention_days,
     monthly_log_quota, allow_custom_domain, custom_domain_limit, allow_auto_dns,
     allow_advanced_rules, sync_interval_seconds, sort_order)
VALUES
    ('free',     'Free',     0,    1,  NULL, 30,  100000,   FALSE, 0, FALSE, FALSE, 60, 1),
    ('starter',  'Starter',  900,  3,  NULL, 60,  500000,   FALSE, 0, FALSE, FALSE, 60, 2),
    ('business', 'Business', 2900, 10, NULL, 180, 2000000,  TRUE,  1, FALSE, FALSE, 60, 3),
    ('scale',    'Scale',    4900, 25, NULL, 365, 5000000,  TRUE,  3, FALSE, TRUE,  60, 4),
    ('hr_pro',   'HR Pro',   7900, 25, NULL, 365, 10000000, TRUE,  5, TRUE,  TRUE,  30, 5)
ON CONFLICT (id) DO NOTHING;
