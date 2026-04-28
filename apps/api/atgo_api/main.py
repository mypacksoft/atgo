"""ATGO API entry point. Single FastAPI app exposing /api/* and /iclock/* (ADMS)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from .routers import (
    adms,
    admin,
    api_keys,
    attendance,
    auth,
    billing,
    branches,
    departments,
    devices,
    dns_providers,
    employee_app,
    employees,
    hr,
    internal,
    odoo,
    sync as sync_router,
    tenants,
)

settings = get_settings()


_INSECURE_DEFAULTS = {
    "dev-secret-change-me",
    "change-me-in-production-please-use-a-long-random-string",
    "",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ----- Production security guards -----
    # Refuse to boot in prod with insecure defaults — this is the single most
    # common deploy mistake. Failing fast saves embarrassing breaches later.
    if settings.ENVIRONMENT == "production":
        if settings.JWT_SECRET in _INSECURE_DEFAULTS or len(settings.JWT_SECRET) < 32:
            raise RuntimeError(
                "JWT_SECRET is missing or too short (>=32 chars). "
                "Generate one with: python -c \"import secrets;print(secrets.token_urlsafe(48))\""
            )
        if "*" in settings.cors_origins_list:
            raise RuntimeError("CORS_ORIGINS must not contain '*' in production")
        if "localhost" in settings.BASE_DOMAIN:
            raise RuntimeError(
                "BASE_DOMAIN cannot contain 'localhost' in production"
            )
    yield


app = FastAPI(
    title="ATGO API",
    version="0.2.0",
    description="Cloud Attendance for ZKTeco — single domain (atgo.io)",
    lifespan=lifespan,
)

# === Middleware (order matters: bottom = innermost) ===
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", include_in_schema=False)
async def health():
    return {"ok": True, "env": settings.ENVIRONMENT}


# ===== Portal API surface (api.atgo.io & {slug}.atgo.io/api/) =====
app.include_router(auth.router,           prefix="/api/auth",           tags=["auth"])
app.include_router(tenants.router,        prefix="/api",                tags=["workspace"])
app.include_router(branches.router,       prefix="/api/branches",       tags=["branches"])
app.include_router(departments.router,    prefix="/api/departments",    tags=["departments"])
app.include_router(devices.router,        prefix="/api/devices",        tags=["devices"])
app.include_router(employees.router,      prefix="/api/employees",      tags=["employees"])
app.include_router(attendance.router,     prefix="/api/attendance",     tags=["attendance"])
app.include_router(billing.router,        prefix="/api/billing",        tags=["billing"])
app.include_router(api_keys.router,       prefix="/api/api-keys",       tags=["api-keys"])
app.include_router(hr.router,             prefix="/api/hr",             tags=["hr"])
app.include_router(sync_router.router,    prefix="/api/sync",           tags=["sync"])
app.include_router(dns_providers.router,  prefix="/api/dns-providers",  tags=["dns"])

# ===== Employee self-service (PWA at {slug}.atgo.io/me) =====
app.include_router(employee_app.router,   prefix="/api/employee",       tags=["employee"])

# ===== Odoo plugin =====
app.include_router(odoo.router,           prefix="/api/odoo",           tags=["odoo"])

# ===== Internal admin (admin.atgo.io) =====
app.include_router(admin.router,          prefix="/api/admin",          tags=["admin"])
app.include_router(internal.router,       prefix="/api/internal",       tags=["internal"])

# ===== ZKTeco device gateway (adms.atgo.io) =====
# Short URL https://atgo.io/{device_code}/iclock/... is rewritten by Caddy to
# /iclock/... so devices keep using the same handlers.
app.include_router(adms.router,           prefix="/iclock",             tags=["adms"])


@app.exception_handler(Exception)
async def fallback_handler(request: Request, exc: Exception):
    if settings.ENVIRONMENT == "development":
        raise exc
    return JSONResponse(status_code=500, content={"error": "internal_error"})
