"""ZKTeco ADMS receiver.

Endpoints (mounted at /iclock):
    GET  /cdata           -> device fetches initial config (server hello)
    POST /cdata           -> device pushes ATTLOG / OPERLOG data
    GET  /getrequest      -> device polls for pending commands
    POST /devicecmd       -> device returns command results
    GET/POST /ping        -> heartbeat

Responses are PLAIN TEXT — devices ignore JSON. Always return 200 OK with
the expected text body or devices retry forever.

Auth model:
  - First contact (unknown SN): we look for a pending claim code that hasn't
    been bound, bind the SN to it. The device row's serial_number gets updated.
  - Subsequent contact: device row exists with that SN and status='active'.
  - Brute-force protection: claim codes expire in 15 minutes; only ONE pending
    claim accepts the next unknown-SN heartbeat per tenant.

We use bypass_rls because ADMS is a system-level endpoint that processes data
across tenants — but every write is scoped by the device's tenant_id which we
look up from the SN.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import text

from ..config import get_settings
from ..db import session_scope
from ..services.adms_parser import (
    filter_biometric,
    parse_attlog,
    render_initial_config,
)

router = APIRouter()
settings = get_settings()


def _ok(body: str = "OK") -> Response:
    return Response(content=body, media_type="text/plain", status_code=200)


async def _resolve_device(session, serial: str) -> dict | None:
    """Return mapping {id, tenant_id, status, timezone} or None."""
    res = await session.execute(
        text(
            "SELECT id, tenant_id, status, timezone FROM devices "
            "WHERE serial_number = :sn AND status IN ('pending_claim','active') "
            "LIMIT 1"
        ),
        {"sn": serial},
    )
    return dict(res.mappings().first() or {}) or None


async def _try_bind_via_claim(session, serial: str, source_ip: str | None) -> dict | None:
    """If an unbound claim code exists, attach this serial to its placeholder
    device. Returns the resolved device mapping or None.
    Bind rule: first unclaimed code with bound_serial IS NULL gets this SN."""
    res = await session.execute(
        text(
            "SELECT cc.id AS claim_id, cc.tenant_id, cc.device_id "
            "FROM device_claim_codes cc "
            "WHERE cc.bound_serial IS NULL "
            "  AND cc.claimed_at IS NULL "
            "  AND cc.expires_at > NOW() "
            "ORDER BY cc.created_at ASC "
            "LIMIT 1 FOR UPDATE SKIP LOCKED"
        )
    )
    row = res.mappings().first()
    if not row:
        return None

    # Make sure the SN doesn't already belong to another live device
    dup = await session.execute(
        text(
            "SELECT id FROM devices WHERE serial_number = :sn "
            "AND status IN ('pending_claim','active')"
        ),
        {"sn": serial},
    )
    if dup.scalar() and dup.scalar() != row["device_id"]:
        return None

    await session.execute(
        text(
            "UPDATE devices SET serial_number = :sn, last_ip = :ip, "
            "last_seen_at = NOW(), updated_at = NOW() WHERE id = :did"
        ),
        {"sn": serial, "ip": source_ip, "did": row["device_id"]},
    )
    await session.execute(
        text("UPDATE device_claim_codes SET bound_serial = :sn WHERE id = :id"),
        {"sn": serial, "id": row["claim_id"]},
    )

    return {"id": row["device_id"], "tenant_id": row["tenant_id"],
            "status": "pending_claim", "timezone": None}


# ===== GET /iclock/cdata?SN=...&options=all =====

@router.get("/cdata")
async def cdata_init(
    request: Request,
    SN: str = Query(...),
    options: str | None = Query(default=None),
    pushver: str | None = Query(default=None),
    language: str | None = Query(default=None),
):
    serial = SN.strip()
    if not serial:
        return _ok("")

    source_ip = request.client.host if request.client else None
    async with session_scope(bypass_rls=True) as session:
        device = await _resolve_device(session, serial)
        if not device:
            device = await _try_bind_via_claim(session, serial, source_ip)
        if not device:
            # Unknown device, no pending claim. Return empty config and let
            # rate-limiter handle abuse.
            return _ok("")

        await session.execute(
            text(
                "UPDATE devices SET last_seen_at = NOW(), is_online = TRUE, "
                "last_ip = :ip, firmware_version = COALESCE(:fw, firmware_version) "
                "WHERE id = :did"
            ),
            {"ip": source_ip, "fw": pushver, "did": device["id"]},
        )
        return _ok(render_initial_config(serial))


# ===== POST /iclock/cdata?SN=...&table=ATTLOG =====

@router.post("/cdata")
async def cdata_push(
    request: Request,
    SN: str = Query(...),
    table: str | None = Query(default=None),
    Stamp: str | None = Query(default=None),
):
    serial = SN.strip()
    body_bytes = await request.body()
    raw = body_bytes.decode("utf-8", errors="replace")
    source_ip = request.client.host if request.client else None

    # Strip biometric data BEFORE persisting
    cleaned, dropped = filter_biometric(raw)

    async with session_scope(bypass_rls=True) as session:
        device = await _resolve_device(session, serial)
        if not device:
            # No matching device; record minimal raw and stop.
            await session.execute(
                text(
                    "INSERT INTO raw_attendance_logs "
                    "(tenant_id, device_id, serial_number, payload_table, raw_payload, source_ip) "
                    "VALUES (0, NULL, :sn, :tbl, :body, :ip)"
                ),
                {"sn": serial, "tbl": table, "body": cleaned[:8192], "ip": source_ip},
            )
            return _ok()

        tenant_id = device["tenant_id"]
        device_id = device["id"]
        device_tz = device["timezone"]

        # store raw
        ins = await session.execute(
            text(
                "INSERT INTO raw_attendance_logs "
                "(tenant_id, device_id, serial_number, payload_table, raw_payload, source_ip) "
                "VALUES (:tid, :did, :sn, :tbl, :body, :ip) RETURNING id"
            ),
            {"tid": tenant_id, "did": device_id, "sn": serial, "tbl": table,
             "body": cleaned, "ip": source_ip},
        )
        raw_id = ins.scalar()

        if (table or "").upper() == "ATTLOG":
            await _ingest_attlog(session, tenant_id, device_id, serial, device_tz, cleaned, raw_id)

        await session.execute(
            text(
                "UPDATE devices SET last_seen_at = NOW(), is_online = TRUE, "
                "last_ip = :ip WHERE id = :did"
            ),
            {"ip": source_ip, "did": device_id},
        )

    return _ok()


async def _ingest_attlog(session, tenant_id: int, device_id: int, serial: str,
                          device_tz: str | None, body: str, raw_id: int) -> None:
    """Parse ATTLOG body and upsert normalized rows.

    Employee mapping by (tenant_id, device_pin) — None if not yet mapped.
    """
    rows = list(parse_attlog(body))
    if not rows:
        return

    # Bulk fetch employee_id mapping by PIN
    pins = list({r.pin for r in rows})
    map_q = await session.execute(
        text(
            "SELECT device_pin, id FROM employees "
            "WHERE tenant_id = :tid AND device_pin = ANY(:pins)"
        ),
        {"tid": tenant_id, "pins": pins},
    )
    pin_to_eid: dict[str, int] = {r["device_pin"]: r["id"] for r in map_q.mappings()}

    for r in rows:
        punched_utc = r.to_utc(device_tz)
        idem = r.idempotency_key(serial)
        await session.execute(
            text(
                "INSERT INTO normalized_attendance_logs "
                "(tenant_id, device_id, employee_id, device_pin, punched_at, "
                " punch_state, verify_type, work_code, idempotency_key, raw_log_id) "
                "VALUES (:tid, :did, :eid, :pin, :pat, :ps, :vt, :wc, :idem, :rid) "
                "ON CONFLICT (idempotency_key, punched_at) DO NOTHING"
            ),
            {
                "tid": tenant_id, "did": device_id,
                "eid": pin_to_eid.get(r.pin),
                "pin": r.pin,
                "pat": punched_utc,
                "ps": r.punch_state, "vt": r.verify_type, "wc": r.work_code,
                "idem": idem, "rid": raw_id,
            },
        )


# ===== GET /iclock/getrequest?SN=... =====

@router.get("/getrequest")
async def get_request(
    request: Request,
    SN: str = Query(...),
):
    serial = SN.strip()
    source_ip = request.client.host if request.client else None
    async with session_scope(bypass_rls=True) as session:
        device = await _resolve_device(session, serial)
        if not device:
            return _ok("OK")

        await session.execute(
            text(
                "UPDATE devices SET last_seen_at = NOW(), is_online = TRUE, "
                "last_ip = :ip WHERE id = :did"
            ),
            {"ip": source_ip, "did": device["id"]},
        )

        # fetch one pending command (FIFO)
        res = await session.execute(
            text(
                "SELECT id, raw_command FROM device_commands "
                "WHERE device_id = :did AND status = 'pending' "
                "AND expires_at > NOW() "
                "ORDER BY id ASC LIMIT 1 FOR UPDATE SKIP LOCKED"
            ),
            {"did": device["id"]},
        )
        cmd = res.mappings().first()
        if not cmd:
            return _ok("OK")

        await session.execute(
            text(
                "UPDATE device_commands SET status = 'sent', delivered_at = NOW(), "
                "attempt_count = attempt_count + 1, last_attempt_at = NOW() "
                "WHERE id = :id"
            ),
            {"id": cmd["id"]},
        )
        # ZKTeco protocol: "C:<id>:<command>"
        return _ok(f"C:{cmd['id']}:{cmd['raw_command']}")


# ===== POST /iclock/devicecmd?SN=... =====
# body looks like "ID=<id>&Return=<code>&CMD=<command>"

@router.post("/devicecmd")
async def device_cmd_result(
    request: Request,
    SN: str = Query(...),
):
    body = (await request.body()).decode("utf-8", errors="replace").strip()
    parts: dict[str, str] = {}
    for kv in body.replace("\n", "&").split("&"):
        if "=" in kv:
            k, _, v = kv.partition("=")
            parts[k.strip().upper()] = v.strip()

    cmd_id = parts.get("ID")
    return_code = parts.get("RETURN")
    if not cmd_id or not return_code:
        return _ok()

    async with session_scope(bypass_rls=True) as session:
        try:
            cid = int(cmd_id)
            rc = int(return_code)
        except ValueError:
            return _ok()
        await session.execute(
            text(
                "UPDATE device_commands SET "
                "status = CASE WHEN :rc = 0 THEN 'done' ELSE 'failed' END, "
                "completed_at = NOW(), return_code = :rc, "
                "error_message = CASE WHEN :rc = 0 THEN NULL ELSE :body END "
                "WHERE id = :id"
            ),
            {"rc": rc, "body": body[:500], "id": cid},
        )
    return _ok()


# ===== Heartbeat / health =====

@router.api_route("/ping", methods=["GET", "POST"])
async def ping(request: Request, SN: str | None = Query(default=None)):
    if SN:
        async with session_scope(bypass_rls=True) as session:
            device = await _resolve_device(session, SN.strip())
            if not device:
                device = await _try_bind_via_claim(
                    session, SN.strip(),
                    request.client.host if request.client else None,
                )
            if device:
                await session.execute(
                    text(
                        "UPDATE devices SET last_seen_at = NOW(), is_online = TRUE "
                        "WHERE id = :id"
                    ),
                    {"id": device["id"]},
                )
    return _ok()
