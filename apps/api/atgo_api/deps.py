"""FastAPI dependencies: auth, tenant resolution, RLS context."""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import SessionLocal
from .models import Tenant, TenantMember, User
from .security import decode_token, hash_api_key

settings = get_settings()


async def db_session() -> AsyncIterator[AsyncSession]:
    """Plain session, no RLS context. Use only for system-level work."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


_NON_TENANT_HOSTS = {"www", "api", "admin", "adms", "cname",
                     "status", "docs", "blog"}


async def _resolve_tenant_id_from_request(
    request: Request, session: AsyncSession
) -> int | None:
    """Resolve tenant_id from the request, in priority order:

    1. Caddy-forwarded slug header  (X-ATGO-Tenant-Slug from Caddyfile)
    2. Host header is a custom domain in tenant_domains
    3. Host header is {slug}.atgo.io / {slug}.atgo.local
    4. Path-based: /<slug>/... when Host == base domain
    5. JWT 'tid' claim (last resort, for direct API access)
    """
    base = settings.BASE_DOMAIN.lower()
    host = request.headers.get("host", "").split(":")[0].lower()

    # 1. Header set by Caddy
    forwarded_slug = request.headers.get("x-atgo-tenant-slug")
    if forwarded_slug:
        slug = forwarded_slug.lower()
        res = await session.execute(
            text("SELECT id FROM tenants WHERE slug = :s AND is_active"), {"s": slug}
        )
        tid = res.scalar()
        if tid:
            return int(tid)

    # 2. Custom domain → tenant_domains lookup
    if host and host != base and not host.endswith(f".{base}"):
        res = await session.execute(
            text(
                "SELECT tenant_id FROM tenant_domains "
                "WHERE normalized_domain = :h AND status IN ('active', 'verified') "
                "AND domain_type = 'custom_domain' LIMIT 1"
            ),
            {"h": host},
        )
        tid = res.scalar()
        if tid:
            return int(tid)

    # 3. Subdomain pattern
    if host.endswith(f".{base}"):
        slug = host[: -(len(base) + 1)]
        if slug and slug not in _NON_TENANT_HOSTS:
            res = await session.execute(
                text("SELECT id FROM tenants WHERE slug = :s AND is_active"),
                {"s": slug},
            )
            tid = res.scalar()
            if tid:
                return int(tid)

    # 4. Path-based: first segment of /api/{slug}/... or /{slug}/...
    path = request.url.path or "/"
    if host == base or host.endswith(":3000") and base in host:
        from ..constants import RESERVED_SUBDOMAINS
        parts = [p for p in path.split("/") if p]
        candidate = None
        if parts and parts[0] not in RESERVED_SUBDOMAINS and parts[0] != "api":
            candidate = parts[0]
        elif len(parts) >= 2 and parts[0] == "api" and parts[1] not in RESERVED_SUBDOMAINS:
            # /api/<slug>/... pattern (rare but supported)
            candidate = parts[1]
        if candidate:
            res = await session.execute(
                text("SELECT id FROM tenants WHERE slug = :s AND is_active"),
                {"s": candidate},
            )
            tid = res.scalar()
            if tid:
                return int(tid)

    # 5. JWT fallback
    authz = request.headers.get("authorization", "")
    if authz.lower().startswith("bearer "):
        payload = decode_token(authz.split(" ", 1)[1].strip())
        if payload and payload.get("tid"):
            return int(payload["tid"])

    return None


def _resolve_tenant_slug_from_host(request: Request) -> str | None:
    """Legacy helper kept for backward compatibility."""
    base = settings.BASE_DOMAIN
    host = request.headers.get("host", "").split(":")[0].lower()
    forwarded_slug = request.headers.get("x-atgo-tenant-slug")
    if forwarded_slug:
        return forwarded_slug.lower()
    if host.endswith(f".{base}"):
        slug = host[: -(len(base) + 1)]
        if slug and slug not in _NON_TENANT_HOSTS:
            return slug
    return None


async def current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(db_session),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    try:
        uid = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token subject")
    user = await session.get(User, uid)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or inactive")
    return user


async def tenant_session(
    request: Request,
    user: User = Depends(current_user),
) -> AsyncIterator[tuple[AsyncSession, Tenant]]:
    """Yields (session, tenant) with RLS scoped to that tenant.

    Resolution order (see _resolve_tenant_id_from_request):
      1. X-ATGO-Tenant-Slug header (Caddy)
      2. Host == verified custom_domain → tenant_domains.tenant_id
      3. Host == {slug}.{base_domain}
      4. Path: /<slug>/... when Host == base_domain (path-based mode)
      5. JWT 'tid' claim
    """
    async with SessionLocal() as session:
        tid = await _resolve_tenant_id_from_request(request, session)
        tenant = await session.get(Tenant, tid) if tid else None
        if tenant is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "tenant not found")

        # confirm membership
        member_q = text(
            "SELECT 1 FROM tenant_members WHERE tenant_id = :tid AND user_id = :uid"
        )
        is_member = await session.execute(member_q, {"tid": tenant.id, "uid": user.id})
        if not is_member.scalar() and not user.is_super_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "not a member of this workspace")

        # bind RLS context for this connection
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant.id)},
        )
        if user.is_super_admin:
            await session.execute(text("SET LOCAL app.bypass_rls = '1'"))

        try:
            yield session, tenant
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def api_key_session(
    request: Request,
    authorization: str | None = Header(default=None),
) -> AsyncIterator[tuple[AsyncSession, int]]:
    """Auth via 'Authorization: Bearer atgo_live_...' API key.

    Used by Odoo plugin and any machine integrations.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing api key")
    full = authorization.split(" ", 1)[1].strip()
    if not full.startswith("atgo_"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid api key format")
    digest = hash_api_key(full)

    async with SessionLocal() as session:
        row = await session.execute(
            text(
                "SELECT id, tenant_id, revoked_at, expires_at "
                "FROM api_keys WHERE key_hash = :h"
            ),
            {"h": digest},
        )
        rec = row.mappings().first()
        if not rec or rec["revoked_at"] is not None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "api key revoked or unknown")

        await session.execute(
            text("UPDATE api_keys SET last_used_at = NOW() WHERE id = :id"),
            {"id": rec["id"]},
        )
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(rec["tenant_id"])},
        )

        try:
            yield session, rec["tenant_id"]
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_client_country(request: Request) -> str:
    """Read country from Cloudflare header, else default."""
    return (request.headers.get("cf-ipcountry") or "DEFAULT").upper()
