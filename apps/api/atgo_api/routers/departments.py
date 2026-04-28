"""Department CRUD with optional parent."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..deps import tenant_session
from ..models import Department

router = APIRouter()


class DeptIn(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    parent_id: int | None = None
    is_active: bool = True


class DeptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    parent_id: int | None
    is_active: bool


@router.get("", response_model=list[DeptOut])
async def list_departments(ctx=Depends(tenant_session)):
    session, tenant = ctx
    res = await session.execute(
        text("SELECT * FROM departments WHERE tenant_id = :tid ORDER BY id"),
        {"tid": tenant.id},
    )
    return [DeptOut.model_validate(dict(r)) for r in res.mappings().all()]


@router.post("", response_model=DeptOut, status_code=status.HTTP_201_CREATED)
async def create_department(payload: DeptIn, ctx=Depends(tenant_session)):
    session, tenant = ctx
    if payload.parent_id is not None:
        parent = await session.get(Department, payload.parent_id)
        if not parent or parent.tenant_id != tenant.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "parent department not found")
    try:
        res = await session.execute(
            text(
                "INSERT INTO departments (tenant_id, code, name, parent_id, is_active) "
                "VALUES (:tid, :c, :n, :p, :ia) RETURNING *"
            ),
            {"tid": tenant.id, "c": payload.code, "n": payload.name,
             "p": payload.parent_id, "ia": payload.is_active},
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "department code already used")
    return DeptOut.model_validate(dict(res.mappings().first()))


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(dept_id: int, ctx=Depends(tenant_session)):
    session, tenant = ctx
    dept = await session.get(Department, dept_id)
    if not dept or dept.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "department not found")
    await session.delete(dept)
