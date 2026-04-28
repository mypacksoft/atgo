"""Employee self-service API.

Mounted at /api/employee/*. Auth: short-lived JWT minted for an
`employee_accounts` row, NOT a `users` row. Tenant context is resolved
from the host (`{slug}.atgo.io`) just like the HR portal.

All routes here are scoped to one employee. They never touch other
employees' data.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import SessionLocal
from ..deps import db_session
from ..schemas import TimesheetRow
from ..security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter()
settings = get_settings()


# --------- schemas ---------

class EmployeeLoginRequest(BaseModel):
    email: EmailStr
    password: str
    workspace_slug: str  # required: which tenant


class EmployeeTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    employee_id: int
    full_name: str
    employee_code: str
    tenant_slug: str


class EmployeeMeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    employee_id: int
    employee_code: str
    full_name: str
    email: str | None
    department_id: int | None
    branch_id: int | None
    is_active: bool


class EmployeeTodayOut(BaseModel):
    work_date: date
    first_check_in: datetime | None
    last_check_out: datetime | None
    total_punches: int
    worked_minutes: int | None
    status: str


class CorrectionRequestIn(BaseModel):
    work_date: date
    requested_check_in: datetime | None = None
    requested_check_out: datetime | None = None
    reason: str = Field(min_length=3, max_length=2000)
    attachment_url: str | None = None


class LeaveRequestIn(BaseModel):
    leave_type: str = Field(pattern="^(annual|sick|unpaid|other)$")
    start_date: date
    end_date: date
    half_day: bool = False
    reason: str | None = None
    attachment_url: str | None = None


class NotificationOut(BaseModel):
    id: int
    kind: str
    title: str
    body: str | None
    read_at: datetime | None
    created_at: datetime


class InviteRequest(BaseModel):
    """HR/admin creates/refreshes an invite for an employee."""
    employee_id: int
    email: EmailStr | None = None


class AcceptInviteRequest(BaseModel):
    invite_token: str
    password: str = Field(min_length=8, max_length=128)


# --------- helpers ---------

EMP_TOKEN_TTL_MIN = 24 * 60  # employee tokens last a day


def _emp_token(account_id: int, tenant_id: int) -> str:
    """Reuse the access-token machinery but scope it as 'emp'."""
    from jose import jwt
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account_id),
        "tid": tenant_id,
        "type": "emp_access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=EMP_TOKEN_TTL_MIN)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


async def _resolve_tenant_by_slug(session: AsyncSession, slug: str) -> int | None:
    res = await session.execute(text("SELECT id FROM tenants WHERE slug = :s"), {"s": slug})
    return res.scalar()


async def employee_session(
    request: Request,
    authorization: str | None = Header(default=None),
):
    """Yields (session, account_row, employee_row) — RLS scoped to that tenant."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token) or {}
    if payload.get("type") != "emp_access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong token type")
    try:
        account_id = int(payload["sub"])
        tenant_id = int(payload["tid"])
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad token")

    async with SessionLocal() as session:
        await session.execute(text("SELECT set_config('app.tenant_id', :tid, true)"),
                              {"tid": str(tenant_id)})
        acc = await session.execute(
            text("SELECT * FROM employee_accounts WHERE id = :id"),
            {"id": account_id},
        )
        acc_row = acc.mappings().first()
        if not acc_row or not acc_row["is_active"]:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "account inactive")

        emp = await session.execute(
            text("SELECT * FROM employees WHERE id = :id"),
            {"id": acc_row["employee_id"]},
        )
        emp_row = emp.mappings().first()
        if not emp_row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "employee missing")

        try:
            yield session, dict(acc_row), dict(emp_row)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# --------- AUTH ---------

@router.post("/login", response_model=EmployeeTokenOut)
async def employee_login(payload: EmployeeLoginRequest,
                          session: AsyncSession = Depends(db_session)):
    tid = await _resolve_tenant_by_slug(session, payload.workspace_slug.lower())
    if not tid:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workspace not found")

    await session.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tid)})
    res = await session.execute(
        text(
            "SELECT a.*, e.full_name, e.employee_code "
            "FROM employee_accounts a JOIN employees e ON e.id = a.employee_id "
            "WHERE a.tenant_id = :tid AND a.email = :em AND a.is_active = TRUE"
        ),
        {"tid": tid, "em": str(payload.email)},
    )
    row = res.mappings().first()
    if not row or not row["password_hash"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    await session.execute(
        text("UPDATE employee_accounts SET last_login_at = NOW() WHERE id = :id"),
        {"id": row["id"]},
    )
    return EmployeeTokenOut(
        access_token=_emp_token(row["id"], tid),
        employee_id=row["employee_id"],
        full_name=row["full_name"],
        employee_code=row["employee_code"],
        tenant_slug=payload.workspace_slug.lower(),
    )


@router.post("/accept-invite", response_model=EmployeeTokenOut)
async def accept_invite(payload: AcceptInviteRequest,
                         session: AsyncSession = Depends(db_session)):
    """Employee turns invite_token into a permanent password."""
    res = await session.execute(
        text(
            "SELECT a.*, t.slug, e.full_name, e.employee_code "
            "FROM employee_accounts a "
            "JOIN tenants t ON t.id = a.tenant_id "
            "JOIN employees e ON e.id = a.employee_id "
            "WHERE a.invite_token = :tok AND a.invite_expires_at > NOW()"
        ),
        {"tok": payload.invite_token},
    )
    row = res.mappings().first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invalid or expired invite")
    await session.execute(
        text(
            "UPDATE employee_accounts SET password_hash = :h, invite_token = NULL, "
            "invite_expires_at = NULL, updated_at = NOW() WHERE id = :id"
        ),
        {"h": hash_password(payload.password), "id": row["id"]},
    )
    return EmployeeTokenOut(
        access_token=_emp_token(row["id"], row["tenant_id"]),
        employee_id=row["employee_id"],
        full_name=row["full_name"],
        employee_code=row["employee_code"],
        tenant_slug=row["slug"],
    )


@router.get("/me", response_model=EmployeeMeOut)
async def employee_me(ctx=Depends(employee_session)):
    _, _, emp = ctx
    return EmployeeMeOut(
        employee_id=emp["id"],
        employee_code=emp["employee_code"],
        full_name=emp["full_name"],
        email=emp.get("email"),
        department_id=emp.get("department_id"),
        branch_id=emp.get("branch_id"),
        is_active=emp["is_active"],
    )


# --------- TODAY + TIMESHEET ---------

@router.get("/attendance/today", response_model=EmployeeTodayOut)
async def attendance_today(ctx=Depends(employee_session)):
    session, _, emp = ctx
    today = date.today()
    fd = datetime.combine(today, time.min, tzinfo=timezone.utc)
    td = fd + timedelta(days=1)
    res = await session.execute(
        text(
            "SELECT MIN(punched_at) AS first_in, MAX(punched_at) AS last_out, "
            "       COUNT(id)::INT AS punches "
            "FROM normalized_attendance_logs "
            "WHERE employee_id = :eid AND punched_at >= :fd AND punched_at < :td"
        ),
        {"eid": emp["id"], "fd": fd, "td": td},
    )
    r = res.mappings().first() or {}
    n = r.get("punches") or 0
    minutes = None
    if n >= 2 and r["first_in"] and r["last_out"]:
        minutes = int((r["last_out"] - r["first_in"]).total_seconds() // 60)
    statu = "absent" if n == 0 else ("missing_checkout" if n == 1 else "present")
    return EmployeeTodayOut(
        work_date=today,
        first_check_in=r.get("first_in"),
        last_check_out=r.get("last_out"),
        total_punches=n,
        worked_minutes=minutes,
        status=statu,
    )


@router.get("/timesheet", response_model=list[TimesheetRow])
async def employee_timesheet(
    ctx=Depends(employee_session),
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
):
    session, _, emp = ctx
    period_start = date(year, month, 1)
    if month == 12:
        period_end = date(year + 1, 1, 1)
    else:
        period_end = date(year, month + 1, 1)

    res = await session.execute(
        text(
            """
            SELECT e.id AS employee_id, e.employee_code, e.full_name,
                   DATE(l.punched_at) AS work_date,
                   MIN(l.punched_at) AS first_check_in,
                   MAX(l.punched_at) AS last_check_out,
                   COUNT(l.id)::INT AS total_punches,
                   CASE WHEN COUNT(l.id) >= 2
                        THEN EXTRACT(EPOCH FROM (MAX(l.punched_at) - MIN(l.punched_at)))::INT / 60
                        ELSE NULL END AS worked_minutes,
                   CASE WHEN COUNT(l.id) = 0 THEN 'absent'
                        WHEN COUNT(l.id) = 1 THEN 'missing_checkout'
                        ELSE 'present' END AS status
            FROM employees e
            LEFT JOIN normalized_attendance_logs l
                ON l.employee_id = e.id
                AND l.punched_at >= :fd AND l.punched_at < :td
            WHERE e.id = :eid
            GROUP BY e.id, e.employee_code, e.full_name, DATE(l.punched_at)
            ORDER BY work_date NULLS LAST
            """
        ),
        {
            "eid": emp["id"],
            "fd": datetime.combine(period_start, time.min, tzinfo=timezone.utc),
            "td": datetime.combine(period_end,   time.min, tzinfo=timezone.utc),
        },
    )
    out = []
    for r in res.mappings().all():
        d = dict(r)
        if d["work_date"] is None:
            continue
        out.append(TimesheetRow(**d))
    return out


# --------- CORRECTION + LEAVE ---------

@router.post("/correction-requests", status_code=status.HTTP_201_CREATED)
async def submit_correction(payload: CorrectionRequestIn,
                             ctx=Depends(employee_session)):
    session, _, emp = ctx
    res = await session.execute(
        text(
            "INSERT INTO attendance_correction_requests "
            "(tenant_id, employee_id, work_date, requested_check_in, "
            " requested_check_out, reason, attachment_url) "
            "VALUES (:tid, :eid, :wd, :ci, :co, :rsn, :att) RETURNING id"
        ),
        {
            "tid": emp["tenant_id"], "eid": emp["id"], "wd": payload.work_date,
            "ci": payload.requested_check_in, "co": payload.requested_check_out,
            "rsn": payload.reason, "att": payload.attachment_url,
        },
    )
    return {"id": res.scalar(), "status": "pending"}


@router.get("/correction-requests")
async def list_my_corrections(ctx=Depends(employee_session), limit: int = 50):
    session, _, emp = ctx
    res = await session.execute(
        text(
            "SELECT id, work_date, requested_check_in, requested_check_out, "
            "       reason, status, review_notes, created_at "
            "FROM attendance_correction_requests "
            "WHERE employee_id = :eid ORDER BY id DESC LIMIT :lim"
        ),
        {"eid": emp["id"], "lim": limit},
    )
    return [dict(r) for r in res.mappings().all()]


@router.post("/leave-requests", status_code=status.HTTP_201_CREATED)
async def submit_leave(payload: LeaveRequestIn, ctx=Depends(employee_session)):
    if payload.start_date > payload.end_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "start_date must be <= end_date")
    session, _, emp = ctx
    res = await session.execute(
        text(
            "INSERT INTO leave_requests "
            "(tenant_id, employee_id, leave_type, start_date, end_date, half_day, "
            " reason, attachment_url) "
            "VALUES (:tid, :eid, :lt, :sd, :ed, :hd, :rsn, :att) RETURNING id"
        ),
        {
            "tid": emp["tenant_id"], "eid": emp["id"],
            "lt": payload.leave_type, "sd": payload.start_date,
            "ed": payload.end_date, "hd": payload.half_day,
            "rsn": payload.reason, "att": payload.attachment_url,
        },
    )
    return {"id": res.scalar(), "status": "pending"}


@router.get("/leave-requests")
async def list_my_leave(ctx=Depends(employee_session), limit: int = 50):
    session, _, emp = ctx
    res = await session.execute(
        text(
            "SELECT id, leave_type, start_date, end_date, half_day, reason, "
            "       status, review_notes, created_at "
            "FROM leave_requests WHERE employee_id = :eid "
            "ORDER BY id DESC LIMIT :lim"
        ),
        {"eid": emp["id"], "lim": limit},
    )
    return [dict(r) for r in res.mappings().all()]


@router.get("/notifications", response_model=list[NotificationOut])
async def list_my_notifications(ctx=Depends(employee_session), limit: int = 50):
    session, acc, _ = ctx
    res = await session.execute(
        text(
            "SELECT id, kind, title, body, read_at, created_at "
            "FROM notifications "
            "WHERE audience = 'employee_account' AND audience_id = :aid "
            "ORDER BY id DESC LIMIT :lim"
        ),
        {"aid": acc["id"], "lim": limit},
    )
    return [NotificationOut(**dict(r)) for r in res.mappings().all()]


@router.post("/notifications/{nid}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(nid: int, ctx=Depends(employee_session)):
    session, acc, _ = ctx
    await session.execute(
        text(
            "UPDATE notifications SET read_at = NOW() "
            "WHERE id = :id AND audience = 'employee_account' AND audience_id = :aid"
        ),
        {"id": nid, "aid": acc["id"]},
    )
