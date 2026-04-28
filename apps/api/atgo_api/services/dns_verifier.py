"""DNS verification for custom domains.

We use stdlib socket / dnspython if available. For MVP we use
asyncio.get_event_loop().getaddrinfo for CNAME-ish best-effort, and
fallback to dnspython when present (recommended in prod).
"""
from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass

try:
    import dns.asyncresolver as _aresolver
    _HAS_DNSPY = True
except ImportError:
    _aresolver = None
    _HAS_DNSPY = False


@dataclass
class DnsCheckResult:
    ok: bool
    actual: list[str]
    error: str | None = None


async def resolve_cname(name: str) -> DnsCheckResult:
    """Return list of CNAME or A targets that the name resolves to."""
    if _HAS_DNSPY:
        try:
            try:
                ans = await _aresolver.resolve(name, "CNAME")
                targets = [str(r.target).rstrip(".") for r in ans]
                return DnsCheckResult(ok=True, actual=targets)
            except Exception:
                ans = await _aresolver.resolve(name, "A")
                targets = [r.address for r in ans]
                return DnsCheckResult(ok=True, actual=targets)
        except Exception as e:
            return DnsCheckResult(ok=False, actual=[], error=str(e))

    # Fallback: getaddrinfo doesn't return CNAME but proves the name resolves
    loop = asyncio.get_event_loop()
    try:
        infos = await loop.getaddrinfo(name, None, type=socket.SOCK_STREAM)
        ips = sorted({info[4][0] for info in infos})
        return DnsCheckResult(ok=True, actual=ips)
    except Exception as e:
        return DnsCheckResult(ok=False, actual=[], error=str(e))


async def resolve_txt(name: str) -> DnsCheckResult:
    if not _HAS_DNSPY:
        return DnsCheckResult(ok=False, actual=[],
                              error="dnspython required for TXT lookup")
    try:
        ans = await _aresolver.resolve(name, "TXT")
        # dnspython TXT records are lists of bytes — concatenate
        targets: list[str] = []
        for r in ans:
            joined = b"".join(r.strings).decode("utf-8", errors="replace")
            targets.append(joined)
        return DnsCheckResult(ok=True, actual=targets)
    except Exception as e:
        return DnsCheckResult(ok=False, actual=[], error=str(e))


async def verify_domain(domain: str, expected_cname: str,
                        txt_name: str | None = None,
                        txt_value: str | None = None) -> tuple[bool, dict]:
    """Verify CNAME (and optionally TXT) for a custom domain.

    Returns (ok, details) — details is what we record into
    `dns_verification_attempts` (or just last_checked snapshot).
    """
    cname = await resolve_cname(domain)
    cname_ok = cname.ok and any(t.lower().rstrip(".") == expected_cname.lower()
                                 for t in cname.actual)

    txt_ok = True
    txt_actual: list[str] = []
    if txt_name and txt_value:
        txt = await resolve_txt(txt_name)
        txt_actual = txt.actual
        txt_ok = txt.ok and any(txt_value in v for v in txt.actual)

    return (cname_ok and txt_ok, {
        "cname": cname.actual,
        "cname_ok": cname_ok,
        "cname_error": cname.error,
        "txt": txt_actual,
        "txt_ok": txt_ok,
    })
