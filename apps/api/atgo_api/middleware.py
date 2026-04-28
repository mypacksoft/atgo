"""HTTP middleware: rate limiting, security headers, IP block.

Applied globally in main.py. Each request runs in O(1) (single Redis EVAL).
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .services.rate_limit import is_blocked_ip, take


def _client_ip(req: Request) -> str:
    # Trust X-Forwarded-For from Caddy
    fwd = req.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return req.client.host if req.client else "0.0.0.0"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = _client_ip(request)
        path = request.url.path

        if await is_blocked_ip(ip):
            return PlainTextResponse("blocked", status_code=403)

        # ADMS endpoints have their own per-device bucket; rest of the API
        # gets a generous per-IP one.
        if path.startswith("/iclock"):
            sn = (request.query_params.get("SN") or "").strip().upper()
            profile, key = ("adms_per_device", sn) if sn else ("adms_unknown_ip", ip)
        elif path.startswith("/api/auth/"):
            profile, key = "auth_per_ip", ip
        elif path.startswith("/api/billing/webhook/"):
            profile, key = "webhook_per_ip", ip
        else:
            profile, key = "api_per_ip", ip

        ok, _ = await take(profile, key)
        if not ok:
            # ADMS responses must be plain-text, otherwise some firmwares
            # treat them as protocol errors and retry too aggressively.
            if path.startswith("/iclock"):
                return PlainTextResponse("OK", status_code=200)
            return JSONResponse({"error": "rate_limited"}, status_code=429)

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        # CSP for portal-served HTML; portal itself sets its own when needed
        return resp
