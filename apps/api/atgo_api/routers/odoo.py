"""Odoo plugin endpoints. Auth via API key (Bearer atgo_live_...)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text

from ..deps import api_key_session

router = APIRouter()


@router.get("/plan-usage")
async def plan_usage(ctx=Depends(api_key_session)):
    session, tenant_id = ctx
    res = await session.execute(
        text(
            "SELECT t.id AS tenant_id, t.slug, t.plan_id, "
            "       (SELECT COUNT(*) FROM devices d WHERE d.tenant_id = t.id "
            "         AND d.status = 'active')::INT AS device_count, "
            "       (SELECT COUNT(*) FROM employees e WHERE e.tenant_id = t.id "
            "         AND e.is_active)::INT AS employee_count "
            "FROM tenants t WHERE t.id = :tid"
        ),
        {"tid": tenant_id},
    )
    row = res.mappings().first()
    return dict(row) if row else {}


@router.get("/devices")
async def odoo_devices(ctx=Depends(api_key_session)):
    session, tenant_id = ctx
    res = await session.execute(
        text(
            "SELECT id, name, serial_number, device_code, model, firmware_version, "
            "status, is_online, last_seen_at, timezone "
            "FROM devices WHERE tenant_id = :tid AND status != 'disabled' "
            "ORDER BY id"
        ),
        {"tid": tenant_id},
    )
    return {"devices": [dict(r) for r in res.mappings().all()]}


@router.get("/attendance-logs")
async def odoo_logs(
    ctx=Depends(api_key_session),
    limit: int = Query(default=500, le=2000),
    after_id: int | None = None,
):
    """Pull unsynced logs. Odoo sends `after_id` to paginate."""
    session, tenant_id = ctx
    clauses = ["tenant_id = :tid", "odoo_synced_at IS NULL"]
    params: dict = {"tid": tenant_id, "lim": limit}
    if after_id:
        clauses.append("id > :after")
        params["after"] = after_id

    res = await session.execute(
        text(
            "SELECT l.id, l.employee_id, l.device_pin, l.punched_at, "
            "  l.punch_state, l.verify_type, d.device_code "
            "FROM normalized_attendance_logs l "
            "LEFT JOIN devices d ON d.id = l.device_id "
            "WHERE " + " AND ".join(clauses) +
            " ORDER BY l.id ASC LIMIT :lim"
        ),
        params,
    )
    rows = []
    for r in res.mappings().all():
        d = dict(r)
        d["punched_at"] = d["punched_at"].isoformat() if d["punched_at"] else None
        rows.append(d)
    return {"logs": rows}


class AckRequest(BaseModel):
    log_ids: list[int]


@router.post("/attendance-logs/ack")
async def ack_logs(payload: AckRequest, ctx=Depends(api_key_session)):
    session, tenant_id = ctx
    if not payload.log_ids:
        return {"acked": 0}
    res = await session.execute(
        text(
            "UPDATE normalized_attendance_logs "
            "SET odoo_synced_at = NOW() "
            "WHERE tenant_id = :tid AND id = ANY(:ids) "
            "AND odoo_synced_at IS NULL"
        ),
        {"tid": tenant_id, "ids": payload.log_ids},
    )
    return {"acked": res.rowcount}


# ============================================================
# Odoo -> ATGO employee push (auto-sync hr.employee into ATGO)
# ============================================================

class OdooEmployeeIn(BaseModel):
    odoo_id: int
    employee_code: str | None = None
    full_name: str
    device_pin: str | None = None        # = hr.employee.barcode
    email: str | None = None
    phone: str | None = None
    department_code: str | None = None
    is_active: bool = True


class UpsertEmployeesRequest(BaseModel):
    employees: list[OdooEmployeeIn]


@router.post("/employees/upsert")
async def upsert_employees(payload: UpsertEmployeesRequest, ctx=Depends(api_key_session)):
    """Odoo plugin pushes hr.employee records here.

    Match priority:
      1. odoo_id == employees.odoo_id  → update
      2. device_pin == employees.device_pin → adopt + set odoo_id
      3. employee_code == employees.employee_code → adopt + set odoo_id
      4. None match AND tenants.auto_create_from_odoo = TRUE → INSERT
    """
    session, tenant_id = ctx
    if not payload.employees:
        return {"created": 0, "updated": 0, "skipped": 0}

    cfg = await session.execute(
        text("SELECT auto_create_from_odoo FROM tenants WHERE id = :tid"),
        {"tid": tenant_id},
    )
    auto_create = bool(cfg.scalar())

    created = updated = skipped = 0
    for e in payload.employees:
        if not e.device_pin:
            skipped += 1
            continue

        # Resolve dept_id by code (optional)
        dept_id = None
        if e.department_code:
            r = await session.execute(
                text("SELECT id FROM departments WHERE tenant_id = :tid AND code = :c"),
                {"tid": tenant_id, "c": e.department_code},
            )
            dept_id = r.scalar()

        # 1. Match by odoo_id
        existing = await session.execute(
            text("SELECT id FROM employees WHERE tenant_id = :tid AND odoo_id = :oid"),
            {"tid": tenant_id, "oid": e.odoo_id},
        )
        eid = existing.scalar()

        # 2. Match by device_pin
        if not eid:
            r = await session.execute(
                text(
                    "SELECT id FROM employees WHERE tenant_id = :tid AND device_pin = :p"
                ),
                {"tid": tenant_id, "p": e.device_pin},
            )
            eid = r.scalar()

        # 3. Match by employee_code
        if not eid and e.employee_code:
            r = await session.execute(
                text(
                    "SELECT id FROM employees WHERE tenant_id = :tid AND employee_code = :c"
                ),
                {"tid": tenant_id, "c": e.employee_code},
            )
            eid = r.scalar()

        if eid:
            await session.execute(
                text(
                    "UPDATE employees SET full_name = :n, "
                    " email = COALESCE(:em, email), phone = COALESCE(:ph, phone), "
                    " device_pin = :p, employee_code = COALESCE(:c, employee_code), "
                    " department_id = COALESCE(:d, department_id), "
                    " is_active = :ia, odoo_id = :oid, "
                    " auto_created = FALSE, source = 'odoo', updated_at = NOW() "
                    "WHERE id = :id"
                ),
                {
                    "n": e.full_name, "em": e.email, "ph": e.phone, "p": e.device_pin,
                    "c": e.employee_code, "d": dept_id, "ia": e.is_active,
                    "oid": e.odoo_id, "id": eid,
                },
            )
            updated += 1
        elif auto_create:
            try:
                code = e.employee_code or f"ODOO-{e.odoo_id}"
                await session.execute(
                    text(
                        "INSERT INTO employees "
                        "(tenant_id, employee_code, device_pin, full_name, email, phone, "
                        " department_id, is_active, odoo_id, auto_created, source) "
                        "VALUES (:tid, :c, :p, :n, :em, :ph, :d, :ia, :oid, FALSE, 'odoo')"
                    ),
                    {
                        "tid": tenant_id, "c": code, "p": e.device_pin, "n": e.full_name,
                        "em": e.email, "ph": e.phone, "d": dept_id, "ia": e.is_active,
                        "oid": e.odoo_id,
                    },
                )
                created += 1
            except Exception:
                skipped += 1
        else:
            skipped += 1

    return {"created": created, "updated": updated, "skipped": skipped}
