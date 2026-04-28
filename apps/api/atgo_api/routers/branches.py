"""Branch CRUD."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..deps import tenant_session
from ..models import Branch

router = APIRouter()


class BranchIn(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    timezone: str | None = None
    address: str | None = None
    is_active: bool = True


class BranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    timezone: str | None
    address: str | None
    is_active: bool


@router.get("", response_model=list[BranchOut])
async def list_branches(ctx=Depends(tenant_session)):
    session, tenant = ctx
    res = await session.execute(
        text("SELECT * FROM branches WHERE tenant_id = :tid ORDER BY id"),
        {"tid": tenant.id},
    )
    return [BranchOut.model_validate(dict(r)) for r in res.mappings().all()]


@router.post("", response_model=BranchOut, status_code=status.HTTP_201_CREATED)
async def create_branch(payload: BranchIn, ctx=Depends(tenant_session)):
    session, tenant = ctx
    try:
        res = await session.execute(
            text(
                "INSERT INTO branches (tenant_id, code, name, timezone, address, is_active) "
                "VALUES (:tid, :c, :n, :tz, :a, :ia) RETURNING *"
            ),
            {"tid": tenant.id, "c": payload.code, "n": payload.name,
             "tz": payload.timezone, "a": payload.address, "ia": payload.is_active},
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "branch code already used")
    return BranchOut.model_validate(dict(res.mappings().first()))


@router.patch("/{branch_id}", response_model=BranchOut)
async def update_branch(branch_id: int, payload: BranchIn, ctx=Depends(tenant_session)):
    session, tenant = ctx
    branch = await session.get(Branch, branch_id)
    if not branch or branch.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "branch not found")
    await session.execute(
        text(
            "UPDATE branches SET code=:c, name=:n, timezone=:tz, address=:a, is_active=:ia "
            "WHERE id = :id"
        ),
        {"c": payload.code, "n": payload.name, "tz": payload.timezone,
         "a": payload.address, "ia": payload.is_active, "id": branch_id},
    )
    await session.refresh(branch)
    return BranchOut.model_validate(branch)


@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch(branch_id: int, ctx=Depends(tenant_session)):
    session, tenant = ctx
    branch = await session.get(Branch, branch_id)
    if not branch or branch.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "branch not found")
    await session.delete(branch)
