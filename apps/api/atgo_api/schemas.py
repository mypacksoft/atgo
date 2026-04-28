"""Pydantic schemas for HTTP request/response."""
from __future__ import annotations

from datetime import datetime, date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .security import normalize_slug, normalize_domain


# ===== Auth =====

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    company_name: str = Field(min_length=1, max_length=200)
    workspace_slug: str = Field(min_length=3, max_length=30)
    country: str | None = Field(default=None, max_length=2)

    @field_validator("workspace_slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        s = normalize_slug(v)
        if len(s) < 3 or len(s) > 30:
            raise ValueError("slug length must be 3-30")
        if s.startswith("-") or s.endswith("-"):
            raise ValueError("slug cannot start or end with -")
        return s


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    user: "UserOut"
    tenant: "TenantOut | None" = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str | None
    locale: str
    timezone: str
    is_super_admin: bool


# ===== Tenant / Workspace =====

class SlugCheckOut(BaseModel):
    available: bool
    slug: str
    workspace_url: str | None = None
    reason: str | None = None
    message: str


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    name: str
    plan_id: str
    primary_domain: str | None
    default_timezone: str
    billing_country: str | None
    is_active: bool


# ===== Domains =====

class DomainCheckOut(BaseModel):
    available: bool
    normalized_domain: str | None = None
    reason: str | None = None
    message: str


class DomainAddRequest(BaseModel):
    domain: str

    @field_validator("domain")
    @classmethod
    def _norm(cls, v: str) -> str:
        n = normalize_domain(v)
        if n is None:
            raise ValueError("invalid domain format")
        return n


class DomainOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    domain: str
    normalized_domain: str
    domain_type: str
    status: str
    is_primary: bool
    cname_target: str | None
    txt_record_name: str | None
    txt_record_value: str | None
    ssl_status: str
    expires_at: datetime | None
    verified_at: datetime | None


# ===== Devices =====

class DeviceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    branch_id: int | None = None
    timezone: str | None = None
    model: str | None = None


class DeviceClaimResponse(BaseModel):
    device_id: int
    device_code: str
    claim_code: str
    claim_expires_at: datetime
    adms_setup: dict


class ClaimVerifyRequest(BaseModel):
    code: str


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    serial_number: str
    device_code: str
    model: str | None
    firmware_version: str | None
    status: str
    is_online: bool
    last_seen_at: datetime | None
    timezone: str | None
    branch_id: int | None
    pending_commands_count: int


# ===== Employees =====

class EmployeeCreateRequest(BaseModel):
    employee_code: str = Field(min_length=1, max_length=50)
    device_pin: str = Field(min_length=1, max_length=20)
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = None
    branch_id: int | None = None
    department_id: int | None = None
    card_number: str | None = None
    is_active: bool = True


class EmployeeUpdateRequest(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    branch_id: int | None = None
    department_id: int | None = None
    card_number: str | None = None
    is_active: bool | None = None


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_code: str
    device_pin: str
    full_name: str
    email: str | None
    phone: str | None
    branch_id: int | None
    department_id: int | None
    is_active: bool
    hired_at: date | None


# ===== Attendance =====

class AttendanceLogOut(BaseModel):
    id: int
    employee_id: int | None
    device_pin: str
    device_id: int
    punched_at: datetime
    punch_state: int | None
    verify_type: int | None


class TimesheetRow(BaseModel):
    employee_id: int
    employee_code: str
    full_name: str
    work_date: date
    first_check_in: datetime | None
    last_check_out: datetime | None
    total_punches: int
    worked_minutes: int | None
    status: str | None


# ===== Pricing / Billing =====

class PricingPlanOut(BaseModel):
    plan_id: str
    name: str
    amount_local: int
    currency: str
    tax_inclusive: bool


class PricingResponse(BaseModel):
    country: str
    currency: str
    providers: list[str]
    default_provider: str
    tax_inclusive: bool
    plans: list[PricingPlanOut]


# Forward references
TokenPair.model_rebuild()
