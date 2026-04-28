"""Dynadot API client.

Dynadot exposes a simple HTTPS API at https://api.dynadot.com/api3.json
authenticated with an API key. Server IPs that call the API must be
allowlisted at Dynadot Tools → API Settings → IP Whitelist.

Reference: https://www.dynadot.com/domain/api3.html

Usage:
    client = DynadotClient(api_key=..., parent_domain="atgo.io")
    await client.add_subdomain_a("phuchao", "203.0.113.10")
    await client.delete_subdomain("phuchao")
    await client.add_subdomain_cname("attendance", "cname.atgo.io")
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx

from ..config import get_settings

settings = get_settings()
log = logging.getLogger(__name__)

DYNADOT_BASE = "https://api.dynadot.com/api3.json"


@dataclass
class DnsRecord:
    """Mirror of Dynadot's per-record shape."""
    record_type: str          # 'A', 'AAAA', 'CNAME', 'TXT', 'MX'
    subdomain: str            # '' for root, 'phuchao' for phuchao.atgo.io
    value: str
    ttl: int = 300
    distance: int | None = None  # for MX


class DynadotError(RuntimeError):
    pass


class DynadotClient:
    def __init__(self, api_key: str, parent_domain: str,
                 server_ipv4: str | None = None, timeout: float = 30.0):
        if not api_key:
            raise ValueError("Dynadot API key required")
        self._key = api_key
        self.parent_domain = parent_domain.lower()
        self.server_ipv4 = server_ipv4
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _call(self, command: str, **params) -> dict:
        params = {"key": self._key, "command": command,
                  "domain": self.parent_domain, **params}
        r = await self._client.get(DYNADOT_BASE, params=params)
        r.raise_for_status()
        data = r.json()
        # Dynadot wraps everything: { "<Command>Response": { "ResponseCode":-1/0, ... } }
        envelope_key = next(iter(data))
        body = data[envelope_key]
        rc = body.get("ResponseCode")
        if rc not in (0, "0"):
            raise DynadotError(f"{command} failed: {body}")
        return body

    # ===== Read =====

    async def get_dns(self) -> list[DnsRecord]:
        """Return current records (does not include nameserver records)."""
        body = await self._call("domain_info")
        domain_data = (body.get("DomainInfoContent") or [{}])[0]
        records_raw = (domain_data.get("NameServerSettings") or {}).get("DNSDataList", [])
        out: list[DnsRecord] = []
        for r in records_raw:
            out.append(DnsRecord(
                record_type=r.get("RecordType", "").upper(),
                subdomain=r.get("SubHost", "") or "",
                value=r.get("Value", ""),
                ttl=int(r.get("TTL", 300) or 300),
                distance=int(r["MxDistance"]) if r.get("MxDistance") else None,
            ))
        return out

    # ===== Write =====

    async def set_dns_records(self, records: list[DnsRecord]) -> None:
        """Replace ALL DNS records for the parent domain in one call.

        Dynadot's set_dns2 is whole-zone — it replaces every record. So we
        always read existing first, merge, then push.
        """
        if not records:
            raise ValueError("must include at least one record (cannot wipe zone)")

        params: dict[str, str] = {}
        for i, r in enumerate(records):
            params[f"record_type{i}"] = r.record_type
            params[f"subdomain{i}"] = r.subdomain
            params[f"record{i}"] = r.value
            if r.ttl:
                params[f"ttl{i}"] = str(r.ttl)
            if r.distance is not None:
                params[f"distance{i}"] = str(r.distance)
        await self._call("set_dns2", **params)

    async def add_subdomain_a(self, subdomain: str, ipv4: str | None = None) -> None:
        """Idempotently add an A record for `<subdomain>.<parent_domain>`."""
        ip = ipv4 or self.server_ipv4
        if not ip:
            raise ValueError("ipv4 required (no server_ipv4 configured)")
        records = await self.get_dns()
        # Replace if exists, else append
        records = [r for r in records
                   if not (r.record_type == "A" and r.subdomain == subdomain)]
        records.append(DnsRecord("A", subdomain, ip, ttl=300))
        await self.set_dns_records(records)

    async def add_subdomain_cname(self, subdomain: str, target: str) -> None:
        records = await self.get_dns()
        records = [r for r in records
                   if not (r.record_type == "CNAME" and r.subdomain == subdomain)]
        records.append(DnsRecord("CNAME", subdomain, target, ttl=300))
        await self.set_dns_records(records)

    async def delete_subdomain(self, subdomain: str) -> None:
        records = await self.get_dns()
        records = [r for r in records if r.subdomain != subdomain]
        if not records:
            log.warning("Refusing to wipe %s — at least one record needed",
                        self.parent_domain)
            return
        await self.set_dns_records(records)


# ===== Module-level convenience =====

_client: DynadotClient | None = None


def get_dynadot_client() -> DynadotClient | None:
    """Returns the singleton, or None when Dynadot is disabled."""
    global _client
    api_key = getattr(settings, "DYNADOT_API_KEY", "")
    if not api_key:
        return None
    if _client is None:
        _client = DynadotClient(
            api_key=api_key,
            parent_domain=getattr(settings, "DYNADOT_PARENT_DOMAIN", settings.BASE_DOMAIN),
            server_ipv4=getattr(settings, "PUBLIC_IPV4", "") or None,
        )
    return _client
