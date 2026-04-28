"""Attendance log query + monthly timesheet + Excel export."""
from __future__ import annotations

import io
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Response
from openpyxl import Workbook
from sqlalchemy import text

from ..deps import tenant_session
from ..schemas import AttendanceLogOut, TimesheetRow

router = APIRouter()


@router.get("/logs", response_model=list[AttendanceLogOut])
async def list_logs(
    ctx=Depends(tenant_session),
    employee_id: int | None = None,
    device_id: int | None = None,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    limit: int = 500,
    offset: int = 0,
):
    session, tenant = ctx
    clauses = ["tenant_id = :tid"]
    params: dict = {"tid": tenant.id, "lim": limit, "off": offset}

    if employee_id:
        clauses.append("employee_id = :eid")
        params["eid"] = employee_id
    if device_id:
        clauses.append("device_id = :did")
        params["did"] = device_id
    if from_date:
        clauses.append("punched_at >= :fd")
        params["fd"] = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
    if to_date:
        clauses.append("punched_at < :td")
        params["td"] = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=timezone.utc)

    sql = (
        "SELECT id, employee_id, device_pin, device_id, punched_at, "
        "punch_state, verify_type "
        "FROM normalized_attendance_logs "
        "WHERE " + " AND ".join(clauses) +
        " ORDER BY punched_at DESC LIMIT :lim OFFSET :off"
    )
    res = await session.execute(text(sql), params)
    return [AttendanceLogOut(**dict(r)) for r in res.mappings().all()]


@router.get("/timesheet", response_model=list[TimesheetRow])
async def monthly_timesheet(
    ctx=Depends(tenant_session),
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    branch_id: int | None = None,
    department_id: int | None = None,
):
    """Compute monthly timesheet on the fly (no batch job needed for MVP)."""
    session, tenant = ctx
    period_start = date(year, month, 1)
    if month == 12:
        period_end = date(year + 1, 1, 1)
    else:
        period_end = date(year, month + 1, 1)

    clauses = ["e.tenant_id = :tid"]
    params: dict = {
        "tid": tenant.id,
        "fd": datetime.combine(period_start, time.min, tzinfo=timezone.utc),
        "td": datetime.combine(period_end, time.min, tzinfo=timezone.utc),
    }
    if branch_id:
        clauses.append("e.branch_id = :bid")
        params["bid"] = branch_id
    if department_id:
        clauses.append("e.department_id = :did")
        params["did"] = department_id

    sql = f"""
        SELECT
            e.id AS employee_id,
            e.employee_code,
            e.full_name,
            DATE(l.punched_at) AS work_date,
            MIN(l.punched_at) AS first_check_in,
            MAX(l.punched_at) AS last_check_out,
            COUNT(l.id)::INT AS total_punches,
            CASE
                WHEN COUNT(l.id) >= 2
                THEN EXTRACT(EPOCH FROM (MAX(l.punched_at) - MIN(l.punched_at)))::INT / 60
                ELSE NULL
            END AS worked_minutes,
            CASE
                WHEN COUNT(l.id) = 0 THEN 'absent'
                WHEN COUNT(l.id) = 1 THEN 'missing_checkout'
                ELSE 'present'
            END AS status
        FROM employees e
        LEFT JOIN normalized_attendance_logs l
            ON l.employee_id = e.id
            AND l.tenant_id = e.tenant_id
            AND l.punched_at >= :fd
            AND l.punched_at < :td
        WHERE {' AND '.join(clauses)}
        GROUP BY e.id, e.employee_code, e.full_name, DATE(l.punched_at)
        ORDER BY e.id, work_date
    """
    res = await session.execute(text(sql), params)
    rows = []
    for r in res.mappings().all():
        d = dict(r)
        if d["work_date"] is None:
            continue  # employee with no logs in period
        rows.append(TimesheetRow(**d))
    return rows


@router.get("/timesheet.xlsx")
async def monthly_timesheet_xlsx(
    ctx=Depends(tenant_session),
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
):
    rows = await monthly_timesheet(ctx=ctx, year=year, month=month,
                                    branch_id=None, department_id=None)
    wb = Workbook()
    ws = wb.active
    ws.title = f"{year}-{month:02d}"
    ws.append([
        "Employee Code", "Name", "Date",
        "First In (UTC)", "Last Out (UTC)", "Punches", "Worked min", "Status",
    ])
    for r in rows:
        ws.append([
            r.employee_code, r.full_name, r.work_date.isoformat(),
            r.first_check_in.isoformat() if r.first_check_in else "",
            r.last_check_out.isoformat() if r.last_check_out else "",
            r.total_punches, r.worked_minutes or "", r.status or "",
        ])
    buf = io.BytesIO()
    wb.save(buf)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="timesheet-{year}-{month:02d}.xlsx"'
        },
    )
