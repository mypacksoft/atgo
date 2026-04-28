"""Internal endpoints — called by Caddy / infra, NOT by users.

Mounted at /api/internal/*. Should NEVER be exposed to public internet
(Caddy/nginx must restrict to localhost or trusted infra).
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import text

from ..config import get_settings
from ..constants import SYSTEM_DOMAIN_BLOCKLIST
from ..db import session_scope
from ..security import normalize_domain

router = APIRouter()
settings = get_settings()


@router.get("/tls-check")
async def tls_check(domain: str = Query(...), request: Request = None) -> Response:
    """Caddy on_demand_tls 'ask' endpoint.

    Returns:
      200 — domain is allowed to receive a Let's Encrypt cert
      404 — refuse (Caddy will not issue cert; protects against random
            domains being pointed at us to farm free SSL)

    Allowlist sources, in order:
      1. The base domain itself (`atgo.io`) and its known subdomains
      2. `{slug}.atgo.io` for any active tenant slug
      3. Verified or active custom domains in `tenant_domains`
    """
    n = normalize_domain(domain)
    if n is None:
        return Response(status_code=404)

    base = settings.BASE_DOMAIN.lower()

    # 1. Base domain + system subdomains
    if n == base or any(n == d for d in SYSTEM_DOMAIN_BLOCKLIST):
        return Response(status_code=200)

    # 2. Tenant default subdomain {slug}.atgo.io
    if n.endswith(f".{base}"):
        slug = n[: -(len(base) + 1)]
        async with session_scope(bypass_rls=True) as s:
            res = await s.execute(
                text("SELECT 1 FROM tenants WHERE slug = :s AND is_active = TRUE"),
                {"s": slug},
            )
            if res.scalar():
                return Response(status_code=200)
        return Response(status_code=404)

    # 3. Custom domain in tenant_domains
    async with session_scope(bypass_rls=True) as s:
        res = await s.execute(
            text(
                "SELECT 1 FROM tenant_domains "
                "WHERE normalized_domain = :n "
                "AND status IN ('verified', 'active') "
                "AND domain_type = 'custom_domain'"
            ),
            {"n": n},
        )
        if res.scalar():
            return Response(status_code=200)

    return Response(status_code=404)


@router.get("/resolve-host")
async def resolve_host(host: str = Query(...)) -> dict:
    """Used by the portal / Next.js middleware to figure out which tenant a
    given Host header belongs to. Returns: { tenant_slug, tenant_id, source }.
    """
    n = normalize_domain(host)
    if n is None:
        return {"tenant_slug": None, "tenant_id": None, "source": "invalid"}

    base = settings.BASE_DOMAIN.lower()

    if n.endswith(f".{base}"):
        slug = n[: -(len(base) + 1)]
        async with session_scope(bypass_rls=True) as s:
            res = await s.execute(
                text("SELECT id, slug FROM tenants WHERE slug = :s AND is_active = TRUE"),
                {"s": slug},
            )
            row = res.mappings().first()
            if row:
                return {"tenant_slug": row["slug"], "tenant_id": row["id"], "source": "subdomain"}

    async with session_scope(bypass_rls=True) as s:
        res = await s.execute(
            text(
                "SELECT t.id, t.slug FROM tenant_domains td "
                "JOIN tenants t ON t.id = td.tenant_id "
                "WHERE td.normalized_domain = :n AND td.status = 'active' "
                "AND td.domain_type = 'custom_domain'"
            ),
            {"n": n},
        )
        row = res.mappings().first()
        if row:
            return {"tenant_slug": row["slug"], "tenant_id": row["id"], "source": "custom_domain"}

    return {"tenant_slug": None, "tenant_id": None, "source": "unknown"}
