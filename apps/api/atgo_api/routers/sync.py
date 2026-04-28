"""Multi-device employee sync — enqueue add/update/disable commands.

ZKTeco protocol (push SDK firmware) uses textual commands like:

    DATA UPDATE USERINFO PIN=1001\tName=John\tPasswd=\tCard=\tGrp=1\tPri=0
    DATA DELETE USERINFO PIN=1001

Devices poll /iclock/getrequest and we return one command per response.
The router below enqueues these into device_commands. The ADMS getrequest
handler (already present) pops them.

This router is mounted at /api/sync/*.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..deps import tenant_session

router = APIRouter()


def _userinfo_cmd(emp: dict) -> str:
    """Format the ZKTeco USERINFO update string. Biometric fields are NEVER
    populated here — push SDK supports `Tmp` for templates but we strip it.
    """
    pin = emp["device_pin"]
    name = (emp["full_name"] or "").replace("\t", " ")
    card = emp.get("card_number") or ""
    return f"DATA UPDATE USERINFO PIN={pin}\tName={name}\tPasswd=\tCard={card}\tGrp=1\tPri=0\tTZ=0000000000000000"


def _delete_cmd(pin: str) -> str:
    return f"DATA DELETE USERINFO PIN={pin}"


class EnqueueIn(BaseModel):
    device_ids: list[int] = Field(min_length=1)
    employee_ids: list[int] | None = None
    """If None, sync all active employees of the tenant onto these devices."""

    action: str = Field(default="upsert", pattern="^(upsert|disable|delete)$")


@router.post("/enqueue")
async def enqueue_sync(payload: EnqueueIn, ctx=Depends(tenant_session)):
    """Enqueue userinfo commands for a set of devices/employees.

    For each (employee, device) pair we:
      - Insert/refresh `employee_device_assignments` row
      - INSERT a row into `device_commands` to be picked up by getrequest
    """
    session, tenant = ctx
    expires = datetime.now(timezone.utc) + timedelta(hours=24)

    # Validate devices
    res = await session.execute(
        text(
            "SELECT id FROM devices WHERE tenant_id = :tid AND id = ANY(:ids) "
            "AND status = 'active'"
        ),
        {"tid": tenant.id, "ids": payload.device_ids},
    )
    valid_devices = [r["id"] for r in res.mappings().all()]
    if not valid_devices:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no active devices in selection")

    # Resolve employees
    if payload.employee_ids:
        emp_res = await session.execute(
            text(
                "SELECT id, device_pin, full_name, card_number, is_active "
                "FROM employees WHERE tenant_id = :tid AND id = ANY(:ids)"
            ),
            {"tid": tenant.id, "ids": payload.employee_ids},
        )
    else:
        emp_res = await session.execute(
            text(
                "SELECT id, device_pin, full_name, card_number, is_active "
                "FROM employees WHERE tenant_id = :tid AND is_active = TRUE"
            ),
            {"tid": tenant.id},
        )
    employees = [dict(r) for r in emp_res.mappings().all()]
    if not employees:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no employees to sync")

    queued = 0
    for emp in employees:
        if payload.action == "upsert":
            cmd_text = _userinfo_cmd(emp)
            cmd_type = "update_user"
        elif payload.action == "disable":
            # Disable in our DB but DO NOT delete from device — admins prefer disable
            cmd_text = _userinfo_cmd({**emp, "full_name": f"DISABLED-{emp['full_name']}"})
            cmd_type = "disable_user"
        else:  # delete
            cmd_text = _delete_cmd(emp["device_pin"])
            cmd_type = "delete_user"

        for did in valid_devices:
            await session.execute(
                text(
                    "INSERT INTO employee_device_assignments "
                    "(tenant_id, employee_id, device_id, sync_status) "
                    "VALUES (:tid, :eid, :did, 'pending') "
                    "ON CONFLICT (employee_id, device_id) DO UPDATE SET "
                    "  sync_status = 'pending', error_message = NULL, "
                    "  last_synced_at = NULL"
                ),
                {"tid": tenant.id, "eid": emp["id"], "did": did},
            )
            await session.execute(
                text(
                    "INSERT INTO device_commands "
                    "(tenant_id, device_id, command_type, raw_command, payload, "
                    " status, expires_at) "
                    "VALUES (:tid, :did, :ct, :rc, CAST(:pl AS jsonb), 'pending', :exp)"
                ),
                {
                    "tid": tenant.id, "did": did, "ct": cmd_type,
                    "rc": cmd_text,
                    "pl": '{"employee_id":' + str(emp["id"]) + '}',
                    "exp": expires,
                },
            )
            await session.execute(
                text(
                    "UPDATE devices SET pending_commands_count = pending_commands_count + 1 "
                    "WHERE id = :did"
                ),
                {"did": did},
            )
            queued += 1

    return {"queued": queued, "devices": len(valid_devices),
            "employees": len(employees)}


@router.get("/status/{employee_id}")
async def employee_sync_status(employee_id: int, ctx=Depends(tenant_session)):
    session, tenant = ctx
    res = await session.execute(
        text(
            "SELECT eda.device_id, eda.sync_status, eda.last_synced_at, "
            "       eda.error_message, d.name AS device_name, d.device_code "
            "FROM employee_device_assignments eda "
            "JOIN devices d ON d.id = eda.device_id "
            "WHERE eda.tenant_id = :tid AND eda.employee_id = :eid"
        ),
        {"tid": tenant.id, "eid": employee_id},
    )
    return [dict(r) for r in res.mappings().all()]


@router.get("/commands")
async def list_commands(
    ctx=Depends(tenant_session),
    device_id: int | None = None,
    status_filter: str | None = None,
    limit: int = 100,
):
    session, tenant = ctx
    clauses = ["tenant_id = :tid"]
    params: dict = {"tid": tenant.id, "lim": limit}
    if device_id:
        clauses.append("device_id = :did")
        params["did"] = device_id
    if status_filter:
        clauses.append("status = :st")
        params["st"] = status_filter
    res = await session.execute(
        text(
            f"SELECT id, device_id, command_type, status, attempt_count, "
            f"  delivered_at, completed_at, return_code, error_message, "
            f"  created_at, expires_at "
            f"FROM device_commands WHERE {' AND '.join(clauses)} "
            f"ORDER BY id DESC LIMIT :lim"
        ),
        params,
    )
    return [dict(r) for r in res.mappings().all()]
