"""Auth: signup (creates user + tenant + owner membership), login, refresh."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..constants import RESERVED_SUBDOMAINS
from ..deps import db_session
from ..models import Tenant, TenantMember, User
from ..schemas import LoginRequest, SignupRequest, TokenPair, TenantOut, UserOut
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter()
settings = get_settings()


def _workspace_url(slug: str) -> str:
    return f"https://{slug}.{settings.BASE_DOMAIN}"


@router.post("/signup", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, session: AsyncSession = Depends(db_session)):
    if payload.workspace_slug in RESERVED_SUBDOMAINS:
        raise HTTPException(status.HTTP_409_CONFLICT, "workspace slug is reserved")

    # check email
    existing = await session.execute(
        text("SELECT id FROM users WHERE email = :e"), {"e": payload.email}
    )
    if existing.scalar():
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

    # check slug
    existing = await session.execute(
        text("SELECT id FROM tenants WHERE slug = :s"), {"s": payload.workspace_slug}
    )
    if existing.scalar():
        raise HTTPException(status.HTTP_409_CONFLICT, "workspace slug already taken")

    user = User(
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    session.add(user)
    await session.flush()

    tenant = Tenant(
        slug=payload.workspace_slug,
        name=payload.company_name,
        plan_id="free",
        billing_country=payload.country.upper() if payload.country else None,
        primary_domain=f"{payload.workspace_slug}.{settings.BASE_DOMAIN}",
    )
    session.add(tenant)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "workspace slug already taken")

    session.add(TenantMember(tenant_id=tenant.id, user_id=user.id, role="owner"))

    # default-subdomain entry in tenant_domains
    await session.execute(
        text(
            "INSERT INTO tenant_domains "
            "(tenant_id, domain, normalized_domain, domain_type, status, is_primary, ssl_status) "
            "VALUES (:tid, :d, :nd, 'default_subdomain', 'active', TRUE, 'issued')"
        ),
        {
            "tid": tenant.id,
            "d": tenant.primary_domain,
            "nd": tenant.primary_domain,
        },
    )
    # seed subscription
    await session.execute(
        text(
            "INSERT INTO subscriptions (tenant_id, plan_id, status, currency, billing_country) "
            "VALUES (:tid, 'free', 'active', 'USD', :c)"
        ),
        {"tid": tenant.id, "c": payload.country.upper() if payload.country else None},
    )

    await session.commit()
    await session.refresh(user)
    await session.refresh(tenant)

    # ----- Auto-DNS for the new tenant subdomain -----
    # Production: register {slug}.atgo.io at the registrar (only if a wildcard
    # record isn't already in place). Dynadot or Cloudflare are supported.
    # Failure here MUST NOT break signup; we fire-and-forget.
    if settings.ENVIRONMENT != "development":
        import asyncio
        from ..services.dynadot import get_dynadot_client

        async def _register_subdomain(slug: str) -> None:
            try:
                d = get_dynadot_client()
                if d is not None:
                    await d.add_subdomain_a(slug)
                # TODO: cloudflare client lookup as a fallback
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    "auto-DNS for %s failed: %s", slug, e
                )

        asyncio.create_task(_register_subdomain(payload.workspace_slug))

    # ----- Local dev hosts-file sync -----
    if settings.ENVIRONMENT == "development" and ".local" in settings.BASE_DOMAIN:
        try:
            import os
            import subprocess
            script = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "..", "..", "scripts", "_atgo_hosts_writer.ps1",
            )
            script = os.path.abspath(script)
            if os.path.exists(script):
                subprocess.Popen(
                    [
                        "powershell.exe", "-NoProfile", "-Command",
                        f"Start-Process powershell -Verb RunAs "
                        f"-ArgumentList '-NoProfile','-ExecutionPolicy','Bypass',"
                        f"'-File','{script}'",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception:
            pass  # never block signup for hosts-sync failure

    return TokenPair(
        access_token=create_access_token(user_id=user.id, tenant_id=tenant.id),
        refresh_token=create_refresh_token(user_id=user.id),
        user=UserOut.model_validate(user),
        tenant=TenantOut.model_validate(tenant),
    )


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, session: AsyncSession = Depends(db_session)):
    res = await session.execute(
        text("SELECT * FROM users WHERE email = :e"), {"e": payload.email}
    )
    row = res.mappings().first()
    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if not row["is_active"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "user inactive")

    user = await session.get(User, row["id"])
    assert user

    # find first tenant membership (user may belong to multiple, we pick most recent)
    res = await session.execute(
        text(
            "SELECT t.* FROM tenants t JOIN tenant_members tm ON tm.tenant_id = t.id "
            "WHERE tm.user_id = :uid ORDER BY tm.created_at DESC LIMIT 1"
        ),
        {"uid": user.id},
    )
    trow = res.mappings().first()
    tenant = await session.get(Tenant, trow["id"]) if trow else None

    await session.execute(
        text("UPDATE users SET last_login_at = NOW() WHERE id = :uid"), {"uid": user.id}
    )

    return TokenPair(
        access_token=create_access_token(user_id=user.id, tenant_id=tenant.id if tenant else None),
        refresh_token=create_refresh_token(user_id=user.id),
        user=UserOut.model_validate(user),
        tenant=TenantOut.model_validate(tenant) if tenant else None,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(refresh_token: str, session: AsyncSession = Depends(db_session)):
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token")
    try:
        uid = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token subject")
    user = await session.get(User, uid)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")

    res = await session.execute(
        text(
            "SELECT t.* FROM tenants t JOIN tenant_members tm ON tm.tenant_id = t.id "
            "WHERE tm.user_id = :uid ORDER BY tm.created_at DESC LIMIT 1"
        ),
        {"uid": user.id},
    )
    trow = res.mappings().first()
    tenant = await session.get(Tenant, trow["id"]) if trow else None

    return TokenPair(
        access_token=create_access_token(user_id=user.id, tenant_id=tenant.id if tenant else None),
        refresh_token=create_refresh_token(user_id=user.id),
        user=UserOut.model_validate(user),
        tenant=TenantOut.model_validate(tenant) if tenant else None,
    )
