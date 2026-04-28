"""API keys: generate (show full once), list (prefix only), revoke."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from ..deps import tenant_session
from ..models import ApiKey
from ..security import generate_api_key

router = APIRouter()


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[str] = Field(default_factory=lambda: ["odoo:read", "odoo:write"])


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreatedOut(ApiKeyOut):
    full_key: str  # shown ONCE


@router.get("", response_model=list[ApiKeyOut])
async def list_keys(ctx=Depends(tenant_session)):
    session, tenant = ctx
    res = await session.execute(
        text(
            "SELECT id, name, prefix, scopes, last_used_at, revoked_at, created_at "
            "FROM api_keys WHERE tenant_id = :tid ORDER BY id DESC"
        ),
        {"tid": tenant.id},
    )
    return [ApiKeyOut.model_validate(dict(r)) for r in res.mappings().all()]


@router.post("", response_model=ApiKeyCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_key(payload: ApiKeyCreate, ctx=Depends(tenant_session)):
    session, tenant = ctx
    full, prefix, key_hash = generate_api_key()
    res = await session.execute(
        text(
            "INSERT INTO api_keys (tenant_id, name, prefix, key_hash, scopes) "
            "VALUES (:tid, :n, :p, :h, :s) "
            "RETURNING id, name, prefix, scopes, last_used_at, revoked_at, created_at"
        ),
        {"tid": tenant.id, "n": payload.name, "p": prefix, "h": key_hash,
         "s": payload.scopes},
    )
    row = dict(res.mappings().first())
    return ApiKeyCreatedOut(full_key=full, **row)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(key_id: int, ctx=Depends(tenant_session)):
    session, tenant = ctx
    key = await session.get(ApiKey, key_id)
    if not key or key.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "api key not found")
    await session.execute(
        text("UPDATE api_keys SET revoked_at = NOW() WHERE id = :id"),
        {"id": key_id},
    )
