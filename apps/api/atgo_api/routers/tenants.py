"""Workspace + domain management."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..constants import (
    PUBLIC_SUFFIX_REJECT,
    RESERVED_SUBDOMAINS,
    SYSTEM_DOMAIN_BLOCKLIST,
)
from ..deps import current_user, db_session, tenant_session
from ..models import Tenant, TenantDomain
from ..schemas import (
    DomainAddRequest,
    DomainCheckOut,
    DomainOut,
    SlugCheckOut,
    TenantOut,
)
from ..security import normalize_domain, normalize_slug, random_token
from ..services.dns_verifier import verify_domain

router = APIRouter()
settings = get_settings()


@router.get("/workspaces/check-slug", response_model=SlugCheckOut)
async def check_slug(slug: str, session: AsyncSession = Depends(db_session)):
    s = normalize_slug(slug)
    if not (3 <= len(s) <= 30):
        return SlugCheckOut(available=False, slug=s, reason="invalid_length",
                            message="Slug must be 3-30 characters.")
    if s.startswith("-") or s.endswith("-"):
        return SlugCheckOut(available=False, slug=s, reason="invalid_format",
                            message="Slug cannot start or end with a dash.")
    if s in RESERVED_SUBDOMAINS:
        return SlugCheckOut(available=False, slug=s, reason="reserved",
                            message="This workspace URL is reserved.")
    res = await session.execute(text("SELECT 1 FROM tenants WHERE slug = :s"), {"s": s})
    if res.scalar():
        return SlugCheckOut(available=False, slug=s, reason="already_taken",
                            message="This workspace URL is already taken.")
    return SlugCheckOut(
        available=True, slug=s,
        workspace_url=f"https://{s}.{settings.BASE_DOMAIN}",
        message="Available.",
    )


@router.get("/domains/check", response_model=DomainCheckOut)
async def check_domain(domain: str, session: AsyncSession = Depends(db_session)):
    n = normalize_domain(domain)
    if n is None:
        return DomainCheckOut(available=False, reason="invalid",
                              message="Invalid domain format.")
    if n in SYSTEM_DOMAIN_BLOCKLIST or n.endswith(f".{settings.BASE_DOMAIN}"):
        return DomainCheckOut(available=False, reason="reserved",
                              message="This domain is reserved.")
    if n in PUBLIC_SUFFIX_REJECT:
        return DomainCheckOut(available=False, reason="invalid",
                              message="Please enter a fully-qualified subdomain.")
    res = await session.execute(
        text(
            "SELECT 1 FROM tenant_domains WHERE normalized_domain = :n "
            "AND status IN ('pending','verified','active','restricted')"
        ),
        {"n": n},
    )
    if res.scalar():
        return DomainCheckOut(available=False, normalized_domain=n,
                              reason="already_claimed",
                              message="This domain is already connected to another workspace.")
    return DomainCheckOut(available=True, normalized_domain=n,
                          message="Domain is available.")


@router.post("/domains", response_model=DomainOut, status_code=status.HTTP_201_CREATED)
async def add_domain(payload: DomainAddRequest, ctx=Depends(tenant_session)):
    session, tenant = ctx
    n = payload.domain
    if n in SYSTEM_DOMAIN_BLOCKLIST or n.endswith(f".{settings.BASE_DOMAIN}"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "reserved domain")

    plan = await session.execute(
        text(
            "SELECT p.allow_custom_domain, p.custom_domain_limit "
            "FROM plans p JOIN tenants t ON t.plan_id = p.id WHERE t.id = :tid"
        ),
        {"tid": tenant.id},
    )
    prow = plan.mappings().first()
    if not prow or not prow["allow_custom_domain"]:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                            "custom domain requires Business plan or above")

    cnt = await session.execute(
        text(
            "SELECT COUNT(*) FROM tenant_domains "
            "WHERE tenant_id = :tid AND domain_type = 'custom_domain' "
            "AND status IN ('pending','verified','active')"
        ),
        {"tid": tenant.id},
    )
    if cnt.scalar() >= prow["custom_domain_limit"]:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                            f"limit reached ({prow['custom_domain_limit']})")

    token = random_token(16)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=72)
    cname = f"cname.{settings.BASE_DOMAIN}"
    txt_name = f"_atgo.{n}"
    txt_value = f"atgo-verify={token}"

    try:
        res = await session.execute(
            text(
                "INSERT INTO tenant_domains "
                "(tenant_id, domain, normalized_domain, domain_type, status, "
                " verification_token, cname_target, txt_record_name, txt_record_value, "
                " ssl_status, expires_at, provider) "
                "VALUES (:tid, :d, :n, 'custom_domain', 'pending', :tok, :cn, :tn, :tv, "
                " 'pending', :exp, 'manual') RETURNING id"
            ),
            {"tid": tenant.id, "d": n, "n": n, "tok": token, "cn": cname,
             "tn": txt_name, "tv": txt_value, "exp": expires_at},
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "domain already claimed by another workspace")

    obj = await session.get(TenantDomain, res.scalar())
    assert obj
    return DomainOut.model_validate(obj)


@router.get("/domains", response_model=list[DomainOut])
async def list_domains(ctx=Depends(tenant_session)):
    session, tenant = ctx
    res = await session.execute(
        text("SELECT * FROM tenant_domains WHERE tenant_id = :tid ORDER BY id"),
        {"tid": tenant.id},
    )
    return [DomainOut.model_validate(dict(r)) for r in res.mappings().all()]


@router.post("/domains/{domain_id}/verify", response_model=DomainOut)
async def verify_domain_endpoint(domain_id: int, ctx=Depends(tenant_session)):
    session, tenant = ctx
    domain = await session.get(TenantDomain, domain_id)
    if not domain or domain.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "domain not found")
    if domain.domain_type != "custom_domain":
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "only custom domains require verification")
    if domain.status in ("active", "verified"):
        return DomainOut.model_validate(domain)
    if domain.expires_at and domain.expires_at < datetime.now(timezone.utc):
        await session.execute(
            text("UPDATE tenant_domains SET status='expired' WHERE id=:id"),
            {"id": domain_id},
        )
        raise HTTPException(status.HTTP_410_GONE, "pending window expired")

    ok, details = await verify_domain(
        domain.normalized_domain,
        expected_cname=domain.cname_target or f"cname.{settings.BASE_DOMAIN}",
        txt_name=domain.txt_record_name,
        txt_value=domain.txt_record_value,
    )

    actual = ",".join(details.get("cname") or []) or None
    await session.execute(
        text(
            "INSERT INTO dns_verification_attempts "
            "(tenant_id, tenant_domain_id, check_type, expected_value, actual_value, "
            " success, error_message) VALUES "
            "(:tid, :did, 'cname', :exp, :act, :ok, :err)"
        ),
        {"tid": tenant.id, "did": domain_id, "exp": domain.cname_target,
         "act": actual, "ok": bool(details.get("cname_ok")),
         "err": details.get("cname_error")},
    )

    new_status = "verified" if ok else "pending"
    await session.execute(
        text(
            "UPDATE tenant_domains SET status = :s, last_checked_at = NOW(), "
            "verified_at = CASE WHEN :s = 'verified' THEN NOW() ELSE verified_at END, "
            "ssl_status = CASE WHEN :s = 'verified' THEN 'pending' ELSE ssl_status END, "
            "updated_at = NOW() WHERE id = :id"
        ),
        {"s": new_status, "id": domain_id},
    )
    if not ok:
        cname_got = details.get("cname") or []
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"DNS not configured yet (expected CNAME -> {domain.cname_target}; got {cname_got})",
        )
    await session.refresh(domain)
    return DomainOut.model_validate(domain)


@router.post("/domains/{domain_id}/set-primary", response_model=DomainOut)
async def set_primary_domain(domain_id: int, ctx=Depends(tenant_session)):
    session, tenant = ctx
    plan = await session.execute(
        text(
            "SELECT p.allow_custom_domain FROM plans p JOIN tenants t "
            "ON t.plan_id = p.id WHERE t.id = :tid"
        ),
        {"tid": tenant.id},
    )
    if not (plan.scalar() or False):
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                            "primary custom domain requires Business+")
    domain = await session.get(TenantDomain, domain_id)
    if not domain or domain.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "domain not found")
    if domain.status not in ("verified", "active"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "domain must be verified first")
    await session.execute(
        text("UPDATE tenant_domains SET is_primary = FALSE WHERE tenant_id = :tid"),
        {"tid": tenant.id},
    )
    await session.execute(
        text(
            "UPDATE tenant_domains SET is_primary = TRUE, "
            "status = CASE WHEN status = 'verified' THEN 'active' ELSE status END, "
            "updated_at = NOW() WHERE id = :id"
        ),
        {"id": domain_id},
    )
    await session.execute(
        text("UPDATE tenants SET primary_domain = :d WHERE id = :tid"),
        {"d": domain.normalized_domain, "tid": tenant.id},
    )
    await session.refresh(domain)
    return DomainOut.model_validate(domain)


@router.delete("/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain(domain_id: int, ctx=Depends(tenant_session)):
    session, tenant = ctx
    domain = await session.get(TenantDomain, domain_id)
    if not domain or domain.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "domain not found")
    if domain.domain_type == "default_subdomain":
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "cannot remove default subdomain")
    if domain.is_primary:
        await session.execute(
            text("UPDATE tenants SET primary_domain = :d WHERE id = :tid"),
            {"d": f"{tenant.slug}.{settings.BASE_DOMAIN}", "tid": tenant.id},
        )
    await session.delete(domain)


@router.get("/me/tenant", response_model=TenantOut)
async def my_tenant(ctx=Depends(tenant_session)):
    session, tenant = ctx
    return TenantOut.model_validate(tenant)


# ===== User locale preference =====

_SUPPORTED_LOCALES = {
    "en", "vi", "zh-CN", "zh-TW", "id", "th", "ms", "fil",
    "hi", "ar", "es", "pt-BR", "ru", "tr", "fr",
}


class LocaleRequest(BaseModel):
    locale: str


@router.post("/me/locale", include_in_schema=False)
async def set_my_locale(
    payload: LocaleRequest,
    user=Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    if payload.locale not in _SUPPORTED_LOCALES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unsupported locale")
    await session.execute(
        text("UPDATE users SET locale = :l, updated_at = NOW() WHERE id = :id"),
        {"l": payload.locale, "id": user.id},
    )
    return {"ok": True, "locale": payload.locale}


# ===== Tenant settings (auto-sync, work week, etc.) =====

class TenantSettingsOut(BaseModel):
    auto_create_from_machine: bool
    auto_create_from_odoo: bool
    work_week_days: int
    standard_shift_minutes: int


class TenantSettingsUpdate(BaseModel):
    auto_create_from_machine: bool | None = None
    auto_create_from_odoo: bool | None = None
    work_week_days: int | None = None
    standard_shift_minutes: int | None = None


@router.get("/me/settings", response_model=TenantSettingsOut)
async def get_tenant_settings(ctx=Depends(tenant_session)):
    session, tenant = ctx
    res = await session.execute(
        text(
            "SELECT auto_create_from_machine, auto_create_from_odoo, "
            "       work_week_days, standard_shift_minutes "
            "FROM tenants WHERE id = :id"
        ),
        {"id": tenant.id},
    )
    return TenantSettingsOut.model_validate(dict(res.mappings().first() or {}))


@router.patch("/me/settings", response_model=TenantSettingsOut)
async def update_tenant_settings(payload: TenantSettingsUpdate, ctx=Depends(tenant_session)):
    session, tenant = ctx
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        return await get_tenant_settings(ctx)
    if "work_week_days" in fields and fields["work_week_days"] not in (5, 6, 7):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "work_week_days must be 5, 6, or 7")
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    fields["id"] = tenant.id
    await session.execute(
        text(f"UPDATE tenants SET {sets}, updated_at = NOW() WHERE id = :id"),
        fields,
    )
    return await get_tenant_settings(ctx)


# tls-check moved to atgo_api.routers.internal — that one validates the slug
# actually exists in `tenants` (and rejects unknown subdomains, preventing
# Let's Encrypt from being asked for cert on non-existent workspaces).
