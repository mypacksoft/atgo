"""Device CRUD + claim flow."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..config import get_settings
from ..deps import tenant_session
from ..models import Device, DeviceClaimCode
from ..schemas import (
    ClaimVerifyRequest,
    DeviceClaimResponse,
    DeviceCreateRequest,
    DeviceOut,
)
from ..security import generate_claim_code, generate_device_code

router = APIRouter()
settings = get_settings()
CLAIM_TTL_MINUTES = 15


@router.get("", response_model=list[DeviceOut])
async def list_devices(ctx=Depends(tenant_session)):
    session, tenant = ctx
    res = await session.execute(
        text("SELECT * FROM devices WHERE tenant_id = :tid ORDER BY id DESC"),
        {"tid": tenant.id},
    )
    return [DeviceOut.model_validate(dict(r)) for r in res.mappings().all()]


@router.post("", response_model=DeviceClaimResponse, status_code=status.HTTP_201_CREATED)
async def create_device_claim(payload: DeviceCreateRequest, ctx=Depends(tenant_session)):
    """Generates a claim code. The actual device row is created when the device
    contacts the ADMS endpoint with its serial — at which point we mint a real
    Device row with status='pending_claim' and link the claim code to it.

    For now we pre-create the Device row with a placeholder serial to keep
    foreign keys clean; the ADMS receiver will UPDATE serial_number on first
    heartbeat from a device that presents this claim code.
    """
    session, tenant = ctx

    # plan device limit check
    plan = await session.execute(
        text(
            "SELECT p.device_limit FROM plans p JOIN tenants t ON t.plan_id = p.id "
            "WHERE t.id = :tid"
        ),
        {"tid": tenant.id},
    )
    limit = plan.scalar()
    if limit is not None:
        cnt = await session.execute(
            text(
                "SELECT COUNT(*) FROM devices WHERE tenant_id = :tid "
                "AND status IN ('pending_claim','active')"
            ),
            {"tid": tenant.id},
        )
        if cnt.scalar() >= limit:
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                                f"device limit ({limit}) reached for current plan")

    # generate unique device_code (4-char marketing label)
    device_code = None
    for _ in range(8):
        candidate = generate_device_code(4)
        exists = await session.execute(
            text("SELECT 1 FROM devices WHERE device_code = :c"), {"c": candidate}
        )
        if not exists.scalar():
            device_code = candidate
            break
    if device_code is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            "could not allocate device code, please retry")

    # placeholder serial; will be updated by ADMS on first heartbeat after claim
    placeholder_sn = f"UNCLAIMED-{device_code}-{int(datetime.now().timestamp())}"

    res = await session.execute(
        text(
            "INSERT INTO devices "
            "(tenant_id, branch_id, serial_number, device_code, name, model, timezone, status) "
            "VALUES (:tid, :bid, :sn, :dc, :name, :model, :tz, 'pending_claim') "
            "RETURNING id"
        ),
        {
            "tid": tenant.id,
            "bid": payload.branch_id,
            "sn": placeholder_sn,
            "dc": device_code,
            "name": payload.name,
            "model": payload.model,
            "tz": payload.timezone,
        },
    )
    device_id = res.scalar()

    claim_code = generate_claim_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=CLAIM_TTL_MINUTES)
    await session.execute(
        text(
            "INSERT INTO device_claim_codes (tenant_id, device_id, code, expires_at) "
            "VALUES (:tid, :did, :c, :exp)"
        ),
        {"tid": tenant.id, "did": device_id, "c": claim_code, "exp": expires_at},
    )

    return DeviceClaimResponse(
        device_id=device_id,
        device_code=device_code,
        claim_code=claim_code,
        claim_expires_at=expires_at,
        adms_setup={
            "host": f"adms.{settings.BASE_DOMAIN}",
            "port": 443,
            "https": True,
            "instructions": [
                f"On the ZKTeco device: Menu → Comm → Cloud Server",
                f"Server: adms.{settings.BASE_DOMAIN}",
                f"Port: 443 (HTTPS)",
                f"Then return here and enter claim code: {claim_code}",
                "Code expires in 15 minutes.",
            ],
        },
    )


@router.post("/claim/verify", response_model=DeviceOut)
async def verify_claim(payload: ClaimVerifyRequest, ctx=Depends(tenant_session)):
    """User enters the claim code; server confirms a device has reported in
    with a matching SN binding. The actual binding is set by the ADMS endpoint
    when the device first connects."""
    session, tenant = ctx
    code = payload.code.strip().upper()

    res = await session.execute(
        text(
            "SELECT * FROM device_claim_codes "
            "WHERE tenant_id = :tid AND code = :c AND claimed_at IS NULL "
            "AND expires_at > NOW()"
        ),
        {"tid": tenant.id, "c": code},
    )
    claim = res.mappings().first()
    if not claim:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "claim code invalid or expired")
    if not claim["bound_serial"]:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "no device has connected with this code yet — verify the device is online")

    # Mark device active
    await session.execute(
        text(
            "UPDATE devices SET status = 'active', updated_at = NOW() "
            "WHERE id = :did"
        ),
        {"did": claim["device_id"]},
    )
    await session.execute(
        text("UPDATE device_claim_codes SET claimed_at = NOW() WHERE id = :id"),
        {"id": claim["id"]},
    )

    device = await session.get(Device, claim["device_id"])
    assert device
    return DeviceOut.model_validate(device)


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(device_id: int, ctx=Depends(tenant_session)):
    session, tenant = ctx
    device = await session.get(Device, device_id)
    if not device or device.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")
    return DeviceOut.model_validate(device)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(device_id: int, ctx=Depends(tenant_session)):
    session, tenant = ctx
    device = await session.get(Device, device_id)
    if not device or device.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")
    # soft delete: mark disabled (do not hard-delete to preserve attendance history)
    await session.execute(
        text("UPDATE devices SET status = 'disabled', updated_at = NOW() WHERE id = :id"),
        {"id": device_id},
    )
