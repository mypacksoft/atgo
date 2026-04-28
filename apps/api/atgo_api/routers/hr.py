"""HR side of correction/leave requests + employee invites.

Mounted at /api/hr/*. Auth via tenant_session (HR/admin user).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text

from ..deps import current_user, tenant_session
from ..security import random_token

router = APIRouter()


class ReviewIn(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    notes: str | None = None


class InviteOut(BaseModel):
    employee_id: int
    invite_url: str
    expires_at: datetime


# --------- review correction ---------

@router.get("/correction-requests")
async def list_corrections(
    ctx=Depends(tenant_session),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = 100,
):
    session, tenant = ctx
    clauses = ["tenant_id = :tid"]
    params: dict = {"tid": tenant.id, "lim": limit}
    if status_filter:
        clauses.append("status = :st")
        params["st"] = status_filter
    res = await session.execute(
        text(
            "SELECT cr.*, e.employee_code, e.full_name "
            "FROM attendance_correction_requests cr "
            "JOIN employees e ON e.id = cr.employee_id "
            "WHERE " + " AND ".join("cr." + c for c in clauses) +
            " ORDER BY cr.id DESC LIMIT :lim"
        ),
        params,
    )
    return [dict(r) for r in res.mappings().all()]


@router.post("/correction-requests/{rid}/review")
async def review_correction(rid: int, payload: ReviewIn,
                              ctx=Depends(tenant_session),
                              user=Depends(current_user)):
    session, tenant = ctx
    res = await session.execute(
        text(
            "SELECT * FROM attendance_correction_requests "
            "WHERE id = :id AND tenant_id = :tid"
        ),
        {"id": rid, "tid": tenant.id},
    )
    row = res.mappings().first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "request not found")
    if row["status"] != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "already reviewed")

    await session.execute(
        text(
            "UPDATE attendance_correction_requests SET "
            "status = :s, reviewed_by = :u, reviewed_at = NOW(), "
            "review_notes = :n, updated_at = NOW() WHERE id = :id"
        ),
        {"s": payload.decision, "u": user.id, "n": payload.notes, "id": rid},
    )
    # Notify employee
    await session.execute(
        text(
            "INSERT INTO notifications "
            "(tenant_id, audience, audience_id, kind, title, body) "
            "SELECT :tid, 'employee_account', a.id, "
            "       'correction_' || :s, "
            "       'Yêu cầu chỉnh công đã được ' || :s, "
            "       :n "
            "FROM employee_accounts a WHERE a.employee_id = :eid"
        ),
        {"tid": tenant.id, "s": payload.decision,
         "n": payload.notes or "", "eid": row["employee_id"]},
    )
    return {"ok": True}


# --------- review leave ---------

@router.get("/leave-requests")
async def list_leaves(
    ctx=Depends(tenant_session),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = 100,
):
    session, tenant = ctx
    clauses = ["tenant_id = :tid"]
    params: dict = {"tid": tenant.id, "lim": limit}
    if status_filter:
        clauses.append("status = :st")
        params["st"] = status_filter
    res = await session.execute(
        text(
            "SELECT lr.*, e.employee_code, e.full_name "
            "FROM leave_requests lr JOIN employees e ON e.id = lr.employee_id "
            "WHERE " + " AND ".join("lr." + c for c in clauses) +
            " ORDER BY lr.id DESC LIMIT :lim"
        ),
        params,
    )
    return [dict(r) for r in res.mappings().all()]


@router.post("/leave-requests/{rid}/review")
async def review_leave(rid: int, payload: ReviewIn,
                        ctx=Depends(tenant_session),
                        user=Depends(current_user)):
    session, tenant = ctx
    res = await session.execute(
        text("SELECT * FROM leave_requests WHERE id = :id AND tenant_id = :tid"),
        {"id": rid, "tid": tenant.id},
    )
    row = res.mappings().first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "request not found")
    if row["status"] != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "already reviewed")

    await session.execute(
        text(
            "UPDATE leave_requests SET status = :s, reviewed_by = :u, "
            "reviewed_at = NOW(), review_notes = :n, updated_at = NOW() "
            "WHERE id = :id"
        ),
        {"s": payload.decision, "u": user.id, "n": payload.notes, "id": rid},
    )
    return {"ok": True}


# --------- employee invites ---------

@router.post("/employees/{eid}/invite", response_model=InviteOut)
async def invite_employee(eid: int,
                            email: EmailStr | None = None,
                            ctx=Depends(tenant_session)):
    """Create or refresh an employee_accounts row + invite token.

    Returns the invite URL to send via email/SMS. The employee POSTs
    to /api/employee/accept-invite to set their password.
    """
    session, tenant = ctx
    emp = await session.execute(
        text("SELECT id, email, full_name FROM employees WHERE id = :id AND tenant_id = :tid"),
        {"id": eid, "tid": tenant.id},
    )
    e = emp.mappings().first()
    if not e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "employee not found")

    use_email = (email and str(email)) or e["email"]
    if not use_email:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "employee has no email; provide one in the request body",
        )
    token = random_token(24)
    expires = datetime.now(timezone.utc) + timedelta(days=7)

    await session.execute(
        text(
            "INSERT INTO employee_accounts "
            "(tenant_id, employee_id, email, invite_token, invite_expires_at, is_active) "
            "VALUES (:tid, :eid, :em, :tok, :exp, TRUE) "
            "ON CONFLICT (employee_id) DO UPDATE SET "
            "  email = EXCLUDED.email, invite_token = EXCLUDED.invite_token, "
            "  invite_expires_at = EXCLUDED.invite_expires_at, "
            "  is_active = TRUE, updated_at = NOW()"
        ),
        {"tid": tenant.id, "eid": eid, "em": str(use_email),
         "tok": token, "exp": expires},
    )
    invite_url = f"https://{tenant.slug}.{tenant.primary_domain.split('.', 1)[1] if tenant.primary_domain else 'atgo.io'}/me/accept-invite?token={token}"
    return InviteOut(employee_id=eid, invite_url=invite_url, expires_at=expires)
