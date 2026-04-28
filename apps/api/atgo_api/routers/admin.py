"""Internal admin portal API.

Mounted at /api/admin/*. Only `users.is_super_admin = TRUE` may call.
Most operations bypass RLS (`app.bypass_rls = '1'`) so we can see across
all tenants. Every admin write goes through audit_logs.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text

from ..deps import current_user, db_session

router = APIRouter()


def _require_admin(user):
    if not user.is_super_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "super admin only")


@router.get("/overview")
async def overview(user=Depends(current_user), session=Depends(db_session)):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    out: dict = {}

    # Tenants by plan
    res = await session.execute(text(
        "SELECT plan_id, COUNT(*)::INT AS n FROM tenants WHERE is_active = TRUE GROUP BY plan_id"
    ))
    out["tenants_by_plan"] = [dict(r) for r in res.mappings().all()]

    # Total tenants / users
    res = await session.execute(text(
        "SELECT COUNT(*) FILTER (WHERE is_active) AS active, "
        "COUNT(*) FILTER (WHERE NOT is_active) AS suspended, COUNT(*) AS total FROM tenants"
    ))
    out["tenants"] = dict(res.mappings().first() or {})

    res = await session.execute(text(
        "SELECT COUNT(*) FILTER (WHERE is_active) AS active, COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE is_super_admin) AS super_admins FROM users"
    ))
    out["users"] = dict(res.mappings().first() or {})

    # Devices
    res = await session.execute(text(
        "SELECT COUNT(*) FILTER (WHERE is_online AND status = 'active') AS online, "
        "COUNT(*) FILTER (WHERE status = 'active') AS active, "
        "COUNT(*) FILTER (WHERE status = 'pending_claim') AS pending, "
        "COUNT(*) AS total FROM devices"
    ))
    out["devices"] = dict(res.mappings().first() or {})

    # Logs activity
    res = await session.execute(text(
        "SELECT COUNT(*) FROM normalized_attendance_logs "
        "WHERE punched_at >= NOW() - INTERVAL '30 days'"
    ))
    out["logs_30d"] = res.scalar()
    res = await session.execute(text(
        "SELECT COUNT(*) FROM normalized_attendance_logs "
        "WHERE punched_at >= NOW() - INTERVAL '24 hours'"
    ))
    out["logs_24h"] = res.scalar()

    # Pending domain verifications
    res = await session.execute(text(
        "SELECT COUNT(*) FROM tenant_domains WHERE status = 'pending' "
        "AND domain_type = 'custom_domain'"
    ))
    out["pending_custom_domains"] = res.scalar()

    # MRR / ARR — sum of monthly_price for active paid subscriptions
    res = await session.execute(text(
        "SELECT COALESCE(SUM(p.monthly_price_usd_cents),0)::BIGINT AS mrr_cents, "
        "COUNT(*) AS paid_subscriptions "
        "FROM subscriptions s JOIN plans p ON p.id = s.plan_id "
        "WHERE s.status = 'active' AND p.monthly_price_usd_cents > 0"
    ))
    row = dict(res.mappings().first() or {"mrr_cents": 0, "paid_subscriptions": 0})
    out["mrr_usd"] = (row["mrr_cents"] or 0) / 100.0
    out["arr_usd"] = out["mrr_usd"] * 12
    out["paid_subscriptions"] = row["paid_subscriptions"]
    arpa = (out["mrr_usd"] / out["paid_subscriptions"]) if out["paid_subscriptions"] else 0
    out["arpa_usd"] = round(arpa, 2)

    # Growth (signups in last 7/30 days)
    res = await session.execute(text(
        "SELECT "
        " COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days')::INT AS new_7d, "
        " COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days')::INT AS new_30d "
        "FROM tenants"
    ))
    out["growth"] = dict(res.mappings().first() or {})

    # Recent signups
    res = await session.execute(text(
        "SELECT id, slug, name, plan_id, created_at "
        "FROM tenants ORDER BY created_at DESC LIMIT 10"
    ))
    out["recent_signups"] = [dict(r) for r in res.mappings().all()]

    return out


# ============================================================
# USERS
# ============================================================

@router.get("/users")
async def list_users(
    user=Depends(current_user), session=Depends(db_session),
    q: str | None = None, super_only: bool = False,
    limit: int = 100, offset: int = 0,
):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    clauses, params = ["1=1"], {"lim": limit, "off": offset}
    if q:
        clauses.append("(u.email ILIKE :q OR u.full_name ILIKE :q)")
        params["q"] = f"%{q}%"
    if super_only:
        clauses.append("u.is_super_admin = TRUE")
    sql = (
        "SELECT u.id, u.email, u.full_name, u.is_super_admin, u.is_active, "
        " u.last_login_at, u.created_at, "
        " (SELECT COUNT(*) FROM tenant_members tm WHERE tm.user_id = u.id)::INT AS workspace_count, "
        " ( SELECT t.id FROM tenant_members tm JOIN tenants t ON t.id = tm.tenant_id "
        "    WHERE tm.user_id = u.id ORDER BY tm.created_at LIMIT 1 ) AS primary_tenant_id, "
        " ( SELECT t.slug FROM tenant_members tm JOIN tenants t ON t.id = tm.tenant_id "
        "    WHERE tm.user_id = u.id ORDER BY tm.created_at LIMIT 1 ) AS primary_tenant_slug, "
        " ( SELECT t.plan_id FROM tenant_members tm JOIN tenants t ON t.id = tm.tenant_id "
        "    WHERE tm.user_id = u.id ORDER BY tm.created_at LIMIT 1 ) AS primary_tenant_plan "
        "FROM users u WHERE " + " AND ".join(clauses) +
        " ORDER BY u.id DESC LIMIT :lim OFFSET :off"
    )
    res = await session.execute(text(sql), params)
    return [dict(r) for r in res.mappings().all()]


@router.post("/users/{uid}/promote")
async def promote_user(uid: int, user=Depends(current_user), session=Depends(db_session)):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    await session.execute(
        text("UPDATE users SET is_super_admin = TRUE WHERE id = :id"), {"id": uid}
    )
    await _audit(session, user.id, "user.promote", "user", str(uid), {})
    return {"ok": True}


@router.post("/users/{uid}/demote")
async def demote_user(uid: int, user=Depends(current_user), session=Depends(db_session)):
    _require_admin(user)
    if uid == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot demote yourself")
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    # Make sure at least one super-admin remains
    cnt = await session.execute(
        text("SELECT COUNT(*) FROM users WHERE is_super_admin = TRUE AND is_active = TRUE")
    )
    if cnt.scalar() <= 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "must keep at least one super admin")
    await session.execute(
        text("UPDATE users SET is_super_admin = FALSE WHERE id = :id"), {"id": uid}
    )
    await _audit(session, user.id, "user.demote", "user", str(uid), {})
    return {"ok": True}


class ResetPwdIn(BaseModel):
    new_password: str


@router.post("/users/{uid}/reset-password")
async def reset_password(uid: int, payload: ResetPwdIn,
                          user=Depends(current_user), session=Depends(db_session)):
    _require_admin(user)
    if len(payload.new_password) < 8:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "password must be >= 8 chars")
    from ..security import hash_password
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    await session.execute(
        text("UPDATE users SET password_hash = :p WHERE id = :id"),
        {"p": hash_password(payload.new_password), "id": uid},
    )
    await _audit(session, user.id, "user.password_reset", "user", str(uid), {})
    return {"ok": True}


class SetActiveIn(BaseModel):
    is_active: bool


@router.post("/users/{uid}/set-active")
async def set_user_active(uid: int, payload: SetActiveIn,
                           user=Depends(current_user), session=Depends(db_session)):
    _require_admin(user)
    if uid == user.id and not payload.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot disable yourself")
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    await session.execute(
        text("UPDATE users SET is_active = :a WHERE id = :id"),
        {"a": payload.is_active, "id": uid},
    )
    await _audit(session, user.id, "user.set_active", "user", str(uid),
                  {"is_active": payload.is_active})
    return {"ok": True}


# ============================================================
# TENANT DETAIL + ACTIONS
# ============================================================

@router.get("/tenants/{tid}")
async def tenant_detail(tid: int, user=Depends(current_user), session=Depends(db_session)):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))

    res = await session.execute(text("SELECT * FROM tenants WHERE id = :id"), {"id": tid})
    tenant = dict(res.mappings().first() or {})
    if not tenant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tenant not found")

    res = await session.execute(text(
        "SELECT u.id, u.email, u.full_name, tm.role, tm.created_at "
        "FROM tenant_members tm JOIN users u ON u.id = tm.user_id "
        "WHERE tm.tenant_id = :tid ORDER BY tm.created_at"
    ), {"tid": tid})
    tenant["members"] = [dict(r) for r in res.mappings().all()]

    res = await session.execute(text("""
        SELECT
          (SELECT COUNT(*) FROM devices WHERE tenant_id = :tid)::INT AS devices_total,
          (SELECT COUNT(*) FROM devices WHERE tenant_id = :tid AND is_online)::INT AS devices_online,
          (SELECT COUNT(*) FROM employees WHERE tenant_id = :tid AND is_active)::INT AS employees,
          (SELECT COUNT(*) FROM normalized_attendance_logs WHERE tenant_id = :tid
            AND punched_at >= NOW() - INTERVAL '30 days')::INT AS logs_30d,
          (SELECT COUNT(*) FROM tenant_domains WHERE tenant_id = :tid
            AND domain_type = 'custom_domain' AND status = 'active')::INT AS custom_domains
    """), {"tid": tid})
    tenant["stats"] = dict(res.mappings().first() or {})

    res = await session.execute(text(
        "SELECT s.*, p.name AS plan_name, p.monthly_price_usd_cents, p.device_limit "
        "FROM subscriptions s JOIN plans p ON p.id = s.plan_id "
        "WHERE s.tenant_id = :tid"
    ), {"tid": tid})
    tenant["subscription"] = dict(res.mappings().first() or {})

    res = await session.execute(text(
        "SELECT * FROM tenant_domains WHERE tenant_id = :tid ORDER BY id"
    ), {"tid": tid})
    tenant["domains"] = [dict(r) for r in res.mappings().all()]

    return tenant


class ChangePlanIn(BaseModel):
    plan_id: str


@router.post("/tenants/{tid}/change-plan")
async def change_plan(tid: int, payload: ChangePlanIn,
                       user=Depends(current_user), session=Depends(db_session)):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    plan = await session.execute(text("SELECT id FROM plans WHERE id = :p"), {"p": payload.plan_id})
    if not plan.scalar():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown plan")
    await session.execute(
        text("UPDATE tenants SET plan_id = :p, updated_at = NOW() WHERE id = :id"),
        {"p": payload.plan_id, "id": tid},
    )
    await session.execute(
        text("UPDATE subscriptions SET plan_id = :p, updated_at = NOW() WHERE tenant_id = :id"),
        {"p": payload.plan_id, "id": tid},
    )
    await _audit(session, user.id, "tenant.change_plan", "tenant", str(tid),
                  {"plan_id": payload.plan_id})
    return {"ok": True}


@router.post("/tenants/{tid}/impersonate")
async def impersonate_tenant(tid: int, user=Depends(current_user), session=Depends(db_session)):
    """Mint a short-lived access token bound to this tenant, scoped to the
    super-admin's identity. Use sparingly — every call is audited."""
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    res = await session.execute(text("SELECT id, slug FROM tenants WHERE id = :id"), {"id": tid})
    t = res.mappings().first()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tenant not found")

    # Ensure the super-admin is a tenant_member so RLS check in tenant_session passes
    await session.execute(
        text(
            "INSERT INTO tenant_members (tenant_id, user_id, role) "
            "VALUES (:tid, :uid, 'admin') ON CONFLICT (tenant_id, user_id) DO NOTHING"
        ),
        {"tid": tid, "uid": user.id},
    )
    await _audit(session, user.id, "tenant.impersonate", "tenant", str(tid), {})

    from ..security import create_access_token
    token = create_access_token(user_id=user.id, tenant_id=tid)
    return {"access_token": token, "tenant_id": tid, "tenant_slug": t["slug"]}


# ============================================================
# SUBSCRIPTIONS
# ============================================================

@router.get("/subscriptions")
async def list_subscriptions(
    user=Depends(current_user), session=Depends(db_session),
    status_filter: str | None = None, plan_id: str | None = None,
    limit: int = 100, offset: int = 0,
):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    clauses, params = ["1=1"], {"lim": limit, "off": offset}
    if status_filter:
        clauses.append("s.status = :st")
        params["st"] = status_filter
    if plan_id:
        clauses.append("s.plan_id = :pl")
        params["pl"] = plan_id
    sql = (
        "SELECT s.*, t.slug AS tenant_slug, t.name AS tenant_name, "
        " p.name AS plan_name, p.monthly_price_usd_cents "
        "FROM subscriptions s "
        "JOIN tenants t ON t.id = s.tenant_id "
        "JOIN plans p ON p.id = s.plan_id "
        "WHERE " + " AND ".join(clauses) +
        " ORDER BY s.id DESC LIMIT :lim OFFSET :off"
    )
    res = await session.execute(text(sql), params)
    return [dict(r) for r in res.mappings().all()]


# ============================================================
# PLANS
# ============================================================

@router.get("/plans")
async def list_plans(user=Depends(current_user), session=Depends(db_session)):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    res = await session.execute(text("SELECT * FROM plans ORDER BY sort_order"))
    return [dict(r) for r in res.mappings().all()]


class PlanUpdate(BaseModel):
    monthly_price_usd_cents: int | None = None
    device_limit: int | None = None
    employee_limit: int | None = None
    log_retention_days: int | None = None
    monthly_log_quota: int | None = None
    allow_custom_domain: bool | None = None
    custom_domain_limit: int | None = None
    allow_auto_dns: bool | None = None
    allow_advanced_rules: bool | None = None
    is_public: bool | None = None


@router.patch("/plans/{plan_id}")
async def update_plan(plan_id: str, payload: PlanUpdate,
                       user=Depends(current_user), session=Depends(db_session)):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        return {"ok": True, "updated": 0}
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    fields["pid"] = plan_id
    res = await session.execute(text(f"UPDATE plans SET {sets} WHERE id = :pid"), fields)
    await _audit(session, user.id, "plan.update", "plan", plan_id, {k: fields[k] for k in fields if k != "pid"})
    return {"ok": True, "updated": res.rowcount}


# ============================================================
# AUDIT LOGS
# ============================================================

@router.get("/audit-logs")
async def list_audit_logs(
    user=Depends(current_user), session=Depends(db_session),
    tenant_id: int | None = None, action: str | None = None,
    actor_user_id: int | None = None, limit: int = 200, offset: int = 0,
):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    clauses, params = ["1=1"], {"lim": limit, "off": offset}
    if tenant_id:
        clauses.append("a.tenant_id = :tid")
        params["tid"] = tenant_id
    if action:
        clauses.append("a.action ILIKE :ac")
        params["ac"] = f"%{action}%"
    if actor_user_id:
        clauses.append("a.actor_user_id = :uid")
        params["uid"] = actor_user_id
    sql = (
        "SELECT a.*, u.email AS actor_email, t.slug AS tenant_slug "
        "FROM audit_logs a "
        "LEFT JOIN users u ON u.id = a.actor_user_id "
        "LEFT JOIN tenants t ON t.id = a.tenant_id "
        "WHERE " + " AND ".join(clauses) +
        " ORDER BY a.id DESC LIMIT :lim OFFSET :off"
    )
    res = await session.execute(text(sql), params)
    return [dict(r) for r in res.mappings().all()]


# ============================================================
# SYSTEM STATS
# ============================================================

@router.get("/system/stats")
async def system_stats(user=Depends(current_user), session=Depends(db_session)):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))

    out: dict = {}

    # Per-table row counts
    res = await session.execute(text("""
        SELECT 'users' AS t, COUNT(*) AS n FROM users UNION ALL
        SELECT 'tenants', COUNT(*) FROM tenants UNION ALL
        SELECT 'devices', COUNT(*) FROM devices UNION ALL
        SELECT 'employees', COUNT(*) FROM employees UNION ALL
        SELECT 'raw_attendance_logs', COUNT(*) FROM raw_attendance_logs UNION ALL
        SELECT 'normalized_attendance_logs', COUNT(*) FROM normalized_attendance_logs UNION ALL
        SELECT 'tenant_domains', COUNT(*) FROM tenant_domains UNION ALL
        SELECT 'subscriptions', COUNT(*) FROM subscriptions UNION ALL
        SELECT 'audit_logs', COUNT(*) FROM audit_logs UNION ALL
        SELECT 'billing_events', COUNT(*) FROM billing_events
        ORDER BY n DESC
    """))
    out["row_counts"] = [dict(r) for r in res.mappings().all()]

    # DB size
    res = await session.execute(text(
        "SELECT pg_size_pretty(pg_database_size(current_database())) AS size, "
        "pg_database_size(current_database()) AS size_bytes"
    ))
    out["database"] = dict(res.mappings().first() or {})

    # Top largest tables
    res = await session.execute(text("""
        SELECT relname AS name,
               pg_size_pretty(pg_total_relation_size(relid)) AS size,
               pg_total_relation_size(relid) AS size_bytes
        FROM pg_catalog.pg_statio_user_tables
        ORDER BY pg_total_relation_size(relid) DESC LIMIT 10
    """))
    out["largest_tables"] = [dict(r) for r in res.mappings().all()]

    # Postgres version
    res = await session.execute(text("SHOW server_version"))
    out["postgres_version"] = res.scalar()

    return out


# ============================================================
# HELPERS
# ============================================================

async def _audit(session, actor_user_id: int, action: str,
                 resource_type: str, resource_id: str, metadata: dict) -> None:
    await session.execute(
        text(
            "INSERT INTO audit_logs (actor_user_id, actor_type, action, "
            " resource_type, resource_id, metadata) "
            "VALUES (:uid, 'admin', :ac, :rt, :rid, CAST(:m AS jsonb))"
        ),
        {"uid": actor_user_id, "ac": action, "rt": resource_type,
         "rid": resource_id, "m": json.dumps(metadata)},
    )


@router.get("/tenants")
async def list_tenants(
    user=Depends(current_user), session=Depends(db_session),
    q: str | None = Query(default=None),
    limit: int = 100, offset: int = 0,
):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    clauses, params = ["1=1"], {"lim": limit, "off": offset}
    if q:
        clauses.append("(slug ILIKE :q OR name ILIKE :q)")
        params["q"] = f"%{q}%"
    sql = (
        "SELECT t.*, "
        "(SELECT COUNT(*) FROM devices d WHERE d.tenant_id = t.id)::INT AS device_count, "
        "(SELECT COUNT(*) FROM employees e WHERE e.tenant_id = t.id)::INT AS employee_count "
        "FROM tenants t WHERE " + " AND ".join(clauses) +
        " ORDER BY t.id DESC LIMIT :lim OFFSET :off"
    )
    res = await session.execute(text(sql), params)
    return [dict(r) for r in res.mappings().all()]


class SuspendIn(BaseModel):
    reason: str


@router.post("/tenants/{tid}/suspend")
async def suspend_tenant(tid: int, payload: SuspendIn,
                          user=Depends(current_user),
                          session=Depends(db_session)):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    await session.execute(
        text(
            "UPDATE tenants SET is_active = FALSE, suspended_at = NOW(), "
            "suspension_reason = :r WHERE id = :id"
        ),
        {"r": payload.reason, "id": tid},
    )
    await session.execute(
        text(
            "INSERT INTO audit_logs (tenant_id, actor_user_id, actor_type, action, "
            " resource_type, resource_id, metadata) "
            "VALUES (:tid, :uid, 'admin', 'tenant.suspend', 'tenant', :rid, CAST(:m AS jsonb))"
        ),
        {"tid": tid, "uid": user.id, "rid": str(tid),
         "m": json.dumps({"reason": payload.reason})},
    )
    return {"ok": True}


@router.post("/tenants/{tid}/unsuspend")
async def unsuspend_tenant(tid: int, user=Depends(current_user),
                            session=Depends(db_session)):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    await session.execute(
        text(
            "UPDATE tenants SET is_active = TRUE, suspended_at = NULL, "
            "suspension_reason = NULL WHERE id = :id"
        ),
        {"id": tid},
    )
    return {"ok": True}


@router.get("/devices")
async def admin_devices(
    user=Depends(current_user), session=Depends(db_session),
    sn: str | None = None, code: str | None = None, limit: int = 50,
):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    clauses, params = ["1=1"], {"lim": limit}
    if sn:
        clauses.append("serial_number ILIKE :sn")
        params["sn"] = f"%{sn}%"
    if code:
        clauses.append("device_code = :cd")
        params["cd"] = code.upper()
    sql = (
        "SELECT d.*, t.slug AS tenant_slug FROM devices d "
        "JOIN tenants t ON t.id = d.tenant_id "
        "WHERE " + " AND ".join(clauses) +
        " ORDER BY d.id DESC LIMIT :lim"
    )
    res = await session.execute(text(sql), params)
    return [dict(r) for r in res.mappings().all()]


@router.get("/domain-disputes")
async def list_disputes(user=Depends(current_user), session=Depends(db_session)):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    res = await session.execute(text(
        "SELECT * FROM domain_disputes ORDER BY created_at DESC LIMIT 200"
    ))
    return [dict(r) for r in res.mappings().all()]


class ReleaseDomainIn(BaseModel):
    normalized_domain: str
    reason: str


@router.post("/domains/release")
async def release_domain(payload: ReleaseDomainIn,
                          user=Depends(current_user),
                          session=Depends(db_session)):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    await session.execute(
        text(
            "UPDATE tenant_domains SET status = 'restricted', updated_at = NOW() "
            "WHERE normalized_domain = :n AND status IN ('pending','verified','active')"
        ),
        {"n": payload.normalized_domain},
    )
    await session.execute(
        text(
            "INSERT INTO audit_logs (actor_user_id, actor_type, action, "
            " resource_type, resource_id, metadata) "
            "VALUES (:uid, 'admin', 'domain.release', 'domain', :n, CAST(:m AS jsonb))"
        ),
        {"uid": user.id, "n": payload.normalized_domain,
         "m": json.dumps({"reason": payload.reason})},
    )
    return {"ok": True}


@router.get("/billing-events")
async def list_billing_events(
    user=Depends(current_user), session=Depends(db_session),
    provider: str | None = None, processed: bool | None = None, limit: int = 100,
):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    clauses, params = ["1=1"], {"lim": limit}
    if provider:
        clauses.append("provider = :p")
        params["p"] = provider
    if processed is True:
        clauses.append("processed_at IS NOT NULL")
    elif processed is False:
        clauses.append("processed_at IS NULL")
    sql = (
        "SELECT id, provider, event_type, signature_verified, processed_at, "
        " error_message, created_at FROM billing_events "
        "WHERE " + " AND ".join(clauses) + " ORDER BY id DESC LIMIT :lim"
    )
    res = await session.execute(text(sql), params)
    return [dict(r) for r in res.mappings().all()]


@router.get("/security-events")
async def security_events(
    user=Depends(current_user), session=Depends(db_session),
    kind: str | None = None, limit: int = 200,
):
    _require_admin(user)
    await session.execute(text("SET LOCAL app.bypass_rls = '1'"))
    clauses, params = ["1=1"], {"lim": limit}
    if kind:
        clauses.append("kind = :k")
        params["k"] = kind
    sql = (
        "SELECT * FROM security_events WHERE " + " AND ".join(clauses) +
        " ORDER BY id DESC LIMIT :lim"
    )
    res = await session.execute(text(sql), params)
    return [dict(r) for r in res.mappings().all()]


class BlockIpIn(BaseModel):
    ip_address: str
    reason: str
    minutes: int | None = None


@router.post("/blocked-ips")
async def block_ip(payload: BlockIpIn, user=Depends(current_user),
                     session=Depends(db_session)):
    _require_admin(user)
    params = {"ip": payload.ip_address, "r": payload.reason}
    if payload.minutes:
        params["m"] = payload.minutes
        until_sql = "NOW() + (:m || ' minutes')::INTERVAL"
    else:
        until_sql = "NULL"
    sql = (
        "INSERT INTO blocked_ips (ip_address, reason, blocked_until) "
        "VALUES (:ip, :r, " + until_sql + ") "
        "ON CONFLICT (ip_address) DO UPDATE SET "
        "  reason = EXCLUDED.reason, blocked_until = EXCLUDED.blocked_until"
    )
    await session.execute(text(sql), params)
    return {"ok": True}
