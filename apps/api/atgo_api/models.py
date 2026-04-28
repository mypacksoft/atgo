"""SQLAlchemy ORM models. Mirrors infra/postgres/init.sql."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


# ---------- Users / Plans / Tenants ----------

class User(Base):
    __tablename__ = "users"

    id:              Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email:           Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash:   Mapped[str] = mapped_column(Text, nullable=False)
    full_name:       Mapped[str | None] = mapped_column(Text)
    locale:          Mapped[str] = mapped_column(String(10), default="en")
    timezone:        Mapped[str] = mapped_column(String(64), default="UTC")
    is_super_admin:  Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active:       Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Plan(Base):
    __tablename__ = "plans"

    id:                       Mapped[str] = mapped_column(Text, primary_key=True)
    name:                     Mapped[str] = mapped_column(Text, nullable=False)
    monthly_price_usd_cents:  Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    device_limit:             Mapped[int | None] = mapped_column(Integer)
    employee_limit:           Mapped[int | None] = mapped_column(Integer)
    log_retention_days:       Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    monthly_log_quota:        Mapped[int | None] = mapped_column(Integer)
    allow_custom_domain:      Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    custom_domain_limit:      Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    allow_auto_dns:           Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_advanced_rules:     Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sync_interval_seconds:    Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    is_public:                Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order:               Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Tenant(Base):
    __tablename__ = "tenants"

    id:                 Mapped[int] = mapped_column(BigInteger, primary_key=True)
    slug:               Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name:               Mapped[str] = mapped_column(Text, nullable=False)
    plan_id:            Mapped[str] = mapped_column(Text, ForeignKey("plans.id"), default="free", nullable=False)
    billing_country:    Mapped[str | None] = mapped_column(CHAR(2))
    default_timezone:   Mapped[str] = mapped_column(String(64), default="UTC")
    default_locale:     Mapped[str] = mapped_column(String(10), default="en")
    primary_domain:     Mapped[str | None] = mapped_column(Text)
    is_active:          Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    suspended_at:       Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspension_reason:  Mapped[str | None] = mapped_column(Text)
    created_at:         Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:         Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantMember(Base):
    __tablename__ = "tenant_members"

    id:         Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:  Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id:    Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role:       Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("tenant_id", "user_id"),)


class TenantDomain(Base):
    __tablename__ = "tenant_domains"

    id:                 Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:          Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    domain:             Mapped[str] = mapped_column(Text, nullable=False)
    normalized_domain:  Mapped[str] = mapped_column(Text, nullable=False)
    domain_type:        Mapped[str] = mapped_column(Text, nullable=False)
    status:             Mapped[str] = mapped_column(Text, nullable=False)
    is_primary:         Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_token: Mapped[str | None] = mapped_column(Text)
    cname_target:       Mapped[str | None] = mapped_column(Text)
    txt_record_name:    Mapped[str | None] = mapped_column(Text)
    txt_record_value:   Mapped[str | None] = mapped_column(Text)
    ssl_status:         Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    provider:           Mapped[str | None] = mapped_column(Text)
    cloudflare_zone_id: Mapped[str | None] = mapped_column(Text)
    expires_at:         Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at:        Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at:         Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:         Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------- Org structure ----------

class Branch(Base):
    __tablename__ = "branches"
    id:        Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    code:      Mapped[str] = mapped_column(Text, nullable=False)
    name:      Mapped[str] = mapped_column(Text, nullable=False)
    timezone:  Mapped[str | None] = mapped_column(String(64))
    address:   Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("tenant_id", "code"),)


class Department(Base):
    __tablename__ = "departments"
    id:         Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:  Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    code:       Mapped[str] = mapped_column(Text, nullable=False)
    name:       Mapped[str] = mapped_column(Text, nullable=False)
    parent_id:  Mapped[int | None] = mapped_column(BigInteger, ForeignKey("departments.id", ondelete="SET NULL"))
    is_active:  Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("tenant_id", "code"),)


# ---------- Devices ----------

class Device(Base):
    __tablename__ = "devices"

    id:                       Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:                Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    branch_id:                Mapped[int | None] = mapped_column(BigInteger, ForeignKey("branches.id", ondelete="SET NULL"))
    serial_number:            Mapped[str] = mapped_column(Text, nullable=False)
    device_code:              Mapped[str] = mapped_column(Text, nullable=False)
    name:                     Mapped[str] = mapped_column(Text, nullable=False)
    model:                    Mapped[str | None] = mapped_column(Text)
    firmware_version:         Mapped[str | None] = mapped_column(Text)
    timezone:                 Mapped[str | None] = mapped_column(String(64))
    secret_hash:              Mapped[str | None] = mapped_column(Text)
    capabilities:             Mapped[dict] = mapped_column(JSONB, default=dict)
    status:                   Mapped[str] = mapped_column(Text, default="pending_claim", nullable=False)
    last_seen_at:             Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_ip:                  Mapped[str | None] = mapped_column(INET)
    is_online:                Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pending_commands_count:   Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attlog_stamp:        Mapped[str | None] = mapped_column(Text)
    last_operlog_stamp:       Mapped[str | None] = mapped_column(Text)
    created_at:               Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:               Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeviceClaimCode(Base):
    __tablename__ = "device_claim_codes"

    id:           Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:    Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    device_id:    Mapped[int | None] = mapped_column(BigInteger, ForeignKey("devices.id", ondelete="CASCADE"))
    code:         Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    bound_serial: Mapped[str | None] = mapped_column(Text)
    claimed_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeviceCommand(Base):
    __tablename__ = "device_commands"

    id:              Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:       Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    device_id:       Mapped[int] = mapped_column(BigInteger, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    command_type:    Mapped[str] = mapped_column(Text, nullable=False)
    raw_command:     Mapped[str] = mapped_column(Text, nullable=False)
    payload:         Mapped[dict] = mapped_column(JSONB, default=dict)
    status:          Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    attempt_count:   Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message:   Mapped[str | None] = mapped_column(Text)
    return_code:     Mapped[int | None] = mapped_column(Integer)
    expires_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------- Employees ----------

class Employee(Base):
    __tablename__ = "employees"

    id:             Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:      Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    branch_id:      Mapped[int | None] = mapped_column(BigInteger, ForeignKey("branches.id", ondelete="SET NULL"))
    department_id:  Mapped[int | None] = mapped_column(BigInteger, ForeignKey("departments.id", ondelete="SET NULL"))
    employee_code:  Mapped[str] = mapped_column(Text, nullable=False)
    device_pin:     Mapped[str] = mapped_column(Text, nullable=False)
    full_name:      Mapped[str] = mapped_column(Text, nullable=False)
    email:          Mapped[str | None] = mapped_column(Text)
    phone:          Mapped[str | None] = mapped_column(Text)
    card_number:    Mapped[str | None] = mapped_column(Text)
    is_active:      Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    hired_at:       Mapped[date | None] = mapped_column(Date)
    terminated_at:  Mapped[date | None] = mapped_column(Date)
    metadata_:      Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "device_pin"),
        UniqueConstraint("tenant_id", "employee_code"),
    )


class EmployeeDeviceAssignment(Base):
    __tablename__ = "employee_device_assignments"

    id:             Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:      Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    employee_id:    Mapped[int] = mapped_column(BigInteger, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    device_id:      Mapped[int] = mapped_column(BigInteger, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    sync_status:    Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message:  Mapped[str | None] = mapped_column(Text)
    created_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("employee_id", "device_id"),)


# ---------- Attendance ----------
# Note: raw_attendance_logs / normalized_attendance_logs are partitioned. We
# write to them with raw SQL to keep the partition routing clean — no ORM model
# is required for those, but here are minimal Read-only mappings if needed.

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id:               Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:        Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    employee_id:      Mapped[int] = mapped_column(BigInteger, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    work_date:        Mapped[date] = mapped_column(Date, nullable=False)
    first_check_in:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_check_out:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_punches:    Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    worked_minutes:   Mapped[int | None] = mapped_column(Integer)
    status:           Mapped[str | None] = mapped_column(Text)
    is_late:          Mapped[bool | None] = mapped_column(Boolean, default=False)
    is_early_leave:   Mapped[bool | None] = mapped_column(Boolean, default=False)
    notes:            Mapped[str | None] = mapped_column(Text)
    updated_at:       Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("employee_id", "work_date"),)


# ---------- Billing ----------

class Subscription(Base):
    __tablename__ = "subscriptions"

    id:                       Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:                Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan_id:                  Mapped[str] = mapped_column(Text, ForeignKey("plans.id"), nullable=False)
    status:                   Mapped[str] = mapped_column(Text, nullable=False)
    payment_provider:         Mapped[str | None] = mapped_column(Text)
    provider_subscription_id: Mapped[str | None] = mapped_column(Text)
    provider_customer_id:     Mapped[str | None] = mapped_column(Text)
    currency:                 Mapped[str | None] = mapped_column(CHAR(3))
    amount_local:             Mapped[int | None] = mapped_column(BigInteger)
    amount_usd_cents:         Mapped[int | None] = mapped_column(Integer)
    billing_country:          Mapped[str | None] = mapped_column(CHAR(2))
    extra_devices_count:      Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_period_start:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end:       Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end:     Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cancelled_at:             Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at:               Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:               Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApiKey(Base):
    __tablename__ = "api_keys"

    id:           Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:    Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id:      Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    name:         Mapped[str] = mapped_column(Text, nullable=False)
    prefix:       Mapped[str] = mapped_column(Text, nullable=False)
    key_hash:     Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    scopes:       Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id:             Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:      Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"))
    actor_user_id:  Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    actor_type:     Mapped[str] = mapped_column(Text, nullable=False)
    action:         Mapped[str] = mapped_column(Text, nullable=False)
    resource_type:  Mapped[str | None] = mapped_column(Text)
    resource_id:    Mapped[str | None] = mapped_column(Text)
    metadata_:      Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    ip_address:     Mapped[str | None] = mapped_column(INET)
    user_agent:     Mapped[str | None] = mapped_column(Text)
    created_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------- Employee self-service ----------

class EmployeeAccount(Base):
    __tablename__ = "employee_accounts"

    id:                Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:         Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    employee_id:       Mapped[int] = mapped_column(BigInteger, ForeignKey("employees.id", ondelete="CASCADE"), unique=True, nullable=False)
    email:             Mapped[str | None] = mapped_column(Text)
    password_hash:     Mapped[str | None] = mapped_column(Text)
    locale:            Mapped[str] = mapped_column(String(10), default="en")
    last_login_at:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invite_token:      Mapped[str | None] = mapped_column(Text)
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active:         Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at:        Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:        Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CorrectionRequest(Base):
    __tablename__ = "attendance_correction_requests"

    id:                  Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:           Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    employee_id:         Mapped[int] = mapped_column(BigInteger, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    work_date:           Mapped[date] = mapped_column(Date, nullable=False)
    requested_check_in:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_check_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason:              Mapped[str] = mapped_column(Text, nullable=False)
    attachment_url:      Mapped[str | None] = mapped_column(Text)
    status:              Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    reviewed_by:         Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at:         Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes:        Mapped[str | None] = mapped_column(Text)
    created_at:          Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:          Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id:             Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:      Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    employee_id:    Mapped[int] = mapped_column(BigInteger, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    leave_type:     Mapped[str] = mapped_column(Text, nullable=False)
    start_date:     Mapped[date] = mapped_column(Date, nullable=False)
    end_date:       Mapped[date] = mapped_column(Date, nullable=False)
    half_day:       Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reason:         Mapped[str | None] = mapped_column(Text)
    attachment_url: Mapped[str | None] = mapped_column(Text)
    status:         Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    reviewed_by:    Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes:   Mapped[str | None] = mapped_column(Text)
    created_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id:          Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:   Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    audience:    Mapped[str] = mapped_column(Text, nullable=False)
    audience_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind:        Mapped[str] = mapped_column(Text, nullable=False)
    title:       Mapped[str] = mapped_column(Text, nullable=False)
    body:        Mapped[str | None] = mapped_column(Text)
    metadata_:   Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    read_at:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DnsProviderAccount(Base):
    __tablename__ = "dns_provider_accounts"

    id:                  Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id:           Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    provider:            Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_api_token: Mapped[str] = mapped_column(Text, nullable=False)
    account_id:          Mapped[str | None] = mapped_column(Text)
    status:              Mapped[str] = mapped_column(Text, default="active", nullable=False)
    last_used_at:        Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at:          Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:          Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
