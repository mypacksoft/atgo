"""Cloudflare auto-DNS integration.

This is a minimal stub: store the user's API token (encrypted with a
symmetric key derived from JWT_SECRET — replace with KMS in prod), list
zones, create CNAME records.

Endpoints:
    POST /api/dns-providers/cloudflare/connect
    GET  /api/dns-providers/cloudflare/zones
    POST /api/dns-providers/cloudflare/create-record
    DELETE /api/dns-providers/cloudflare/disconnect
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from ..config import get_settings
from ..deps import tenant_session

router = APIRouter()
settings = get_settings()
CF_API = "https://api.cloudflare.com/client/v4"


# Tiny symmetric "encryption" — XOR + HMAC tag. Fine for stub; do NOT
# use in production. Swap for libsodium/Fernet/KMS.
def _key() -> bytes:
    return hashlib.sha256(settings.JWT_SECRET.encode()).digest()


def _encrypt(plain: str) -> str:
    k = _key()
    raw = plain.encode()
    nonce = os.urandom(12)
    stream = b""
    counter = 0
    while len(stream) < len(raw):
        stream += hashlib.sha256(k + nonce + counter.to_bytes(4, "big")).digest()
        counter += 1
    ct = bytes(a ^ b for a, b in zip(raw, stream[: len(raw)]))
    tag = hmac.new(k, nonce + ct, hashlib.sha256).digest()[:16]
    return base64.b64encode(nonce + tag + ct).decode()


def _decrypt(token: str) -> str:
    k = _key()
    blob = base64.b64decode(token)
    nonce, tag, ct = blob[:12], blob[12:28], blob[28:]
    if not hmac.compare_digest(
        hmac.new(k, nonce + ct, hashlib.sha256).digest()[:16], tag
    ):
        raise ValueError("invalid token")
    stream = b""
    counter = 0
    while len(stream) < len(ct):
        stream += hashlib.sha256(k + nonce + counter.to_bytes(4, "big")).digest()
        counter += 1
    return bytes(a ^ b for a, b in zip(ct, stream[: len(ct)])).decode()


async def _cf_get(token: str, path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=15) as cli:
        r = await cli.get(f"{CF_API}{path}",
                           headers={"Authorization": f"Bearer {token}"},
                           params=params or {})
        if r.status_code >= 400:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                                 f"cloudflare: {r.text[:200]}")
        return r.json()


async def _cf_post(token: str, path: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as cli:
        r = await cli.post(f"{CF_API}{path}", json=body,
                            headers={"Authorization": f"Bearer {token}"})
        if r.status_code >= 400:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                                 f"cloudflare: {r.text[:200]}")
        return r.json()


class ConnectIn(BaseModel):
    api_token: str


@router.post("/cloudflare/connect")
async def cf_connect(payload: ConnectIn, ctx=Depends(tenant_session)):
    session, tenant = ctx
    # plan must allow auto DNS (HR Pro+)
    plan = await session.execute(
        text(
            "SELECT p.allow_auto_dns FROM plans p JOIN tenants t "
            "ON t.plan_id = p.id WHERE t.id = :tid"
        ),
        {"tid": tenant.id},
    )
    if not (plan.scalar() or False):
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                            "auto DNS requires HR Pro plan or above")

    # Verify token works by hitting /user/tokens/verify
    try:
        await _cf_get(payload.api_token, "/user/tokens/verify")
    except HTTPException:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                             "invalid Cloudflare API token")

    enc = _encrypt(payload.api_token)
    await session.execute(
        text(
            "INSERT INTO dns_provider_accounts "
            "(tenant_id, provider, encrypted_api_token, status) "
            "VALUES (:tid, 'cloudflare', :enc, 'active') "
            "ON CONFLICT (tenant_id, provider) DO UPDATE SET "
            "  encrypted_api_token = EXCLUDED.encrypted_api_token, "
            "  status = 'active', updated_at = NOW()"
        ),
        {"tid": tenant.id, "enc": enc},
    )
    return {"connected": True}


@router.get("/cloudflare/zones")
async def cf_zones(ctx=Depends(tenant_session)):
    session, tenant = ctx
    res = await session.execute(
        text(
            "SELECT encrypted_api_token FROM dns_provider_accounts "
            "WHERE tenant_id = :tid AND provider = 'cloudflare' AND status = 'active'"
        ),
        {"tid": tenant.id},
    )
    enc = res.scalar()
    if not enc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cloudflare not connected")
    token = _decrypt(enc)
    data = await _cf_get(token, "/zones", {"per_page": 50})
    return {
        "zones": [
            {"id": z["id"], "name": z["name"], "status": z["status"]}
            for z in data.get("result", [])
        ]
    }


class CreateRecordIn(BaseModel):
    zone_id: str
    record_name: str       # full hostname e.g. attendance.abcschool.com
    cname_target: str      # cname.atgo.io


@router.post("/cloudflare/create-record")
async def cf_create_record(payload: CreateRecordIn,
                             ctx=Depends(tenant_session)):
    session, tenant = ctx
    res = await session.execute(
        text(
            "SELECT encrypted_api_token FROM dns_provider_accounts "
            "WHERE tenant_id = :tid AND provider = 'cloudflare' AND status = 'active'"
        ),
        {"tid": tenant.id},
    )
    enc = res.scalar()
    if not enc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cloudflare not connected")
    token = _decrypt(enc)
    body = {
        "type": "CNAME",
        "name": payload.record_name,
        "content": payload.cname_target,
        "ttl": 300,
        "proxied": False,
    }
    out = await _cf_post(token, f"/zones/{payload.zone_id}/dns_records", body)
    return {"created": True, "result": out.get("result")}


@router.delete("/cloudflare/disconnect")
async def cf_disconnect(ctx=Depends(tenant_session)):
    session, tenant = ctx
    await session.execute(
        text(
            "UPDATE dns_provider_accounts SET status = 'disconnected', "
            "updated_at = NOW() WHERE tenant_id = :tid AND provider = 'cloudflare'"
        ),
        {"tid": tenant.id},
    )
    return {"disconnected": True}
