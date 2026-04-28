"""Employee CRUD."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..deps import tenant_session
from ..models import Employee
from ..schemas import EmployeeCreateRequest, EmployeeOut, EmployeeUpdateRequest

router = APIRouter()


@router.get("", response_model=list[EmployeeOut])
async def list_employees(
    ctx=Depends(tenant_session),
    is_active: bool | None = None,
    branch_id: int | None = None,
    department_id: int | None = None,
    limit: int = 200,
    offset: int = 0,
):
    session, tenant = ctx
    clauses = ["tenant_id = :tid"]
    params: dict = {"tid": tenant.id, "lim": limit, "off": offset}
    if is_active is not None:
        clauses.append("is_active = :ia")
        params["ia"] = is_active
    if branch_id is not None:
        clauses.append("branch_id = :bid")
        params["bid"] = branch_id
    if department_id is not None:
        clauses.append("department_id = :did")
        params["did"] = department_id

    res = await session.execute(
        text(
            "SELECT * FROM employees WHERE "
            + " AND ".join(clauses)
            + " ORDER BY id DESC LIMIT :lim OFFSET :off"
        ),
        params,
    )
    return [EmployeeOut.model_validate(dict(r)) for r in res.mappings().all()]


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee(payload: EmployeeCreateRequest, ctx=Depends(tenant_session)):
    session, tenant = ctx
    try:
        res = await session.execute(
            text(
                "INSERT INTO employees "
                "(tenant_id, branch_id, department_id, employee_code, device_pin, "
                " full_name, email, phone, card_number, is_active) "
                "VALUES (:tid, :bid, :did, :code, :pin, :name, :email, :phone, :card, :ia) "
                "RETURNING *"
            ),
            {
                "tid": tenant.id,
                "bid": payload.branch_id,
                "did": payload.department_id,
                "code": payload.employee_code,
                "pin": payload.device_pin,
                "name": payload.full_name,
                "email": str(payload.email) if payload.email else None,
                "phone": payload.phone,
                "card": payload.card_number,
                "ia": payload.is_active,
            },
        )
    except IntegrityError as e:
        await session.rollback()
        msg = "duplicate employee_code or device_pin"
        if "device_pin" in str(e.orig).lower():
            msg = "device_pin already in use"
        elif "employee_code" in str(e.orig).lower():
            msg = "employee_code already in use"
        raise HTTPException(status.HTTP_409_CONFLICT, msg)

    row = res.mappings().first()
    assert row
    return EmployeeOut.model_validate(dict(row))


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(employee_id: int, ctx=Depends(tenant_session)):
    session, tenant = ctx
    emp = await session.get(Employee, employee_id)
    if not emp or emp.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "employee not found")
    return EmployeeOut.model_validate(emp)


@router.patch("/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: int, payload: EmployeeUpdateRequest, ctx=Depends(tenant_session)
):
    session, tenant = ctx
    emp = await session.get(Employee, employee_id)
    if not emp or emp.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "employee not found")

    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        return EmployeeOut.model_validate(emp)

    sets: list[str] = []
    params: dict = {"id": employee_id}
    for k, v in fields.items():
        sets.append(f"{k} = :{k}")
        params[k] = str(v) if k == "email" and v is not None else v

    sets.append("updated_at = NOW()")
    await session.execute(
        text(f"UPDATE employees SET {', '.join(sets)} WHERE id = :id"),
        params,
    )
    await session.refresh(emp)
    return EmployeeOut.model_validate(emp)


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(employee_id: int, ctx=Depends(tenant_session)):
    """Soft delete: mark inactive. Hard delete preserved attendance history."""
    session, tenant = ctx
    emp = await session.get(Employee, employee_id)
    if not emp or emp.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "employee not found")
    await session.execute(
        text(
            "UPDATE employees SET is_active = FALSE, terminated_at = CURRENT_DATE, "
            "updated_at = NOW() WHERE id = :id"
        ),
        {"id": employee_id},
    )
