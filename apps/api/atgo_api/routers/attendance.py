"""Attendance log query + monthly timesheet + Excel export + dashboard."""
from __future__ import annotations

import calendar
import io
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Response
from openpyxl import Workbook
from sqlalchemy import text

from ..deps import tenant_session
from ..schemas import AttendanceLogOut, TimesheetRow

router = APIRouter()


# ============================================================
# Currently clocked-in employees (Nhân viên hiện diện)
# ============================================================

@router.get("/presence")
async def list_presence(ctx=Depends(tenant_session)):
    """Employees currently checked in (last punch was check-in, no check-out yet)."""
    session, tenant = ctx
    res = await session.execute(
        text(
            "SELECT p.employee_id, p.last_in_at, p.device_id, "
            "  e.employee_code, e.full_name, e.device_pin, "
            "  d.name AS device_name, d.device_code, "
            "  dep.name AS department_name "
            "FROM employee_presence p "
            "JOIN employees e ON e.id = p.employee_id "
            "LEFT JOIN devices d ON d.id = p.device_id "
            "LEFT JOIN departments dep ON dep.id = e.department_id "
            "WHERE p.tenant_id = :tid "
            "ORDER BY p.last_in_at DESC LIMIT 500"
        ),
        {"tid": tenant.id},
    )
    return [dict(r) for r in res.mappings().all()]


# ============================================================
# Dashboard: P/A/L/H/W matrix (Odoo-style)
# ============================================================

@router.get("/dashboard")
async def attendance_dashboard(
    ctx=Depends(tenant_session),
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    department_id: int | None = None,
    branch_id: int | None = None,
):
    """Employee × day grid with status code per cell.

    Codes:
      P – Present (>=1 punch on this day)
      A – Absent (work day, no punch, no leave, not holiday)
      L – Leave (approved leave_request covers this day)
      H – Holiday (in tenant holidays table)
      W – Weekend (Sun, plus Sat if work_week_days <= 5)
      \u2014 – Before hire / after termination
    """
    session, tenant = ctx
    period_start = date(year, month, 1)
    days_in_month = calendar.monthrange(year, month)[1]
    period_end = date(year, month, days_in_month)

    cfg = await session.execute(
        text("SELECT work_week_days FROM tenants WHERE id = :tid"),
        {"tid": tenant.id},
    )
    work_week_days = int(cfg.scalar() or 6)

    # Employees in scope
    clauses = ["e.tenant_id = :tid", "e.is_active = TRUE"]
    params: dict = {"tid": tenant.id}
    if department_id:
        clauses.append("e.department_id = :did")
        params["did"] = department_id
    if branch_id:
        clauses.append("e.branch_id = :bid")
        params["bid"] = branch_id

    emp_res = await session.execute(
        text(
            "SELECT e.id, e.employee_code, e.full_name, e.device_pin, "
            " e.hired_at, e.terminated_at, "
            " d.name AS department_name "
            "FROM employees e "
            "LEFT JOIN departments d ON d.id = e.department_id "
            "WHERE " + " AND ".join(clauses) +
            " ORDER BY e.id LIMIT 1000"
        ),
        params,
    )
    employees = [dict(r) for r in emp_res.mappings().all()]
    emp_ids = [e["id"] for e in employees]

    # Holidays for the month
    hol_res = await session.execute(
        text(
            "SELECT holiday_date FROM holidays "
            "WHERE tenant_id = :tid AND holiday_date BETWEEN :s AND :e"
        ),
        {"tid": tenant.id, "s": period_start, "e": period_end},
    )
    holidays = {r["holiday_date"] for r in hol_res.mappings().all()}

    # Leave requests covering this month (only approved)
    leave_res = await session.execute(
        text(
            "SELECT employee_id, start_date, end_date "
            "FROM leave_requests "
            "WHERE tenant_id = :tid AND status = 'approved' "
            "AND start_date <= :pe AND end_date >= :ps"
        ),
        {"tid": tenant.id, "pe": period_end, "ps": period_start},
    )
    leaves: dict[int, set] = {}
    for r in leave_res.mappings().all():
        s = max(r["start_date"], period_start)
        e = min(r["end_date"], period_end)
        cur = s
        while cur <= e:
            leaves.setdefault(r["employee_id"], set()).add(cur)
            cur += timedelta(days=1)

    # Punches per (employee, day) for the month
    punches: dict[int, dict[date, int]] = {}
    if emp_ids:
        p_res = await session.execute(
            text(
                "SELECT employee_id, DATE(punched_at) AS d, COUNT(*)::INT AS n "
                "FROM normalized_attendance_logs "
                "WHERE tenant_id = :tid AND employee_id = ANY(:ids) "
                "  AND punched_at >= :ps AND punched_at < :pe "
                "GROUP BY employee_id, DATE(punched_at)"
            ),
            {
                "tid": tenant.id, "ids": emp_ids,
                "ps": datetime.combine(period_start, time.min, tzinfo=timezone.utc),
                "pe": datetime.combine(period_end + timedelta(days=1), time.min, tzinfo=timezone.utc),
            },
        )
        for r in p_res.mappings().all():
            punches.setdefault(r["employee_id"], {})[r["d"]] = r["n"]

    # Build the matrix
    def status_for(eid: int, d: date) -> str:
        # Before hire / after term
        # (skipped: hired_at/terminated_at column comparisons need lookup — handled
        # outside the inner loop)
        if d in holidays:
            return "H"
        weekday = d.weekday()  # 0=Mon, 6=Sun
        if weekday == 6:
            return "W"
        if weekday == 5 and work_week_days <= 5:
            return "W"
        if d in leaves.get(eid, set()):
            return "L"
        if punches.get(eid, {}).get(d, 0) > 0:
            return "P"
        return "A"

    rows = []
    for emp in employees:
        cells = []
        hire = emp.get("hired_at")
        term = emp.get("terminated_at")
        present = absent = leave = holiday = weekend = 0
        for day in range(1, days_in_month + 1):
            d = date(year, month, day)
            if (hire and d < hire) or (term and d > term):
                code = "-"
            else:
                code = status_for(emp["id"], d)
            cells.append({"day": day, "status": code,
                          "punches": punches.get(emp["id"], {}).get(d, 0)})
            if code == "P":   present += 1
            elif code == "A": absent += 1
            elif code == "L": leave += 1
            elif code == "H": holiday += 1
            elif code == "W": weekend += 1
        rows.append({
            "employee_id": emp["id"],
            "employee_code": emp["employee_code"],
            "full_name": emp["full_name"],
            "department": emp["department_name"],
            "device_pin": emp["device_pin"],
            "cells": cells,
            "summary": {"P": present, "A": absent, "L": leave,
                        "H": holiday, "W": weekend},
        })

    return {
        "year": year,
        "month": month,
        "days_in_month": days_in_month,
        "work_week_days": work_week_days,
        "holidays": sorted(d.isoformat() for d in holidays),
        "rows": rows,
    }


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
