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
