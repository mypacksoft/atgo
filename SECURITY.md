# Security policy

## Reporting a vulnerability

Please report security issues **privately** via email rather than opening a
public GitHub issue:

**security@atgo.io**

Encrypted reports welcome — PGP key on request.

We aim to acknowledge reports within **48 hours** and triage within **7 days**.

## What we consider in scope

- Authentication / authorization bypass (tenant isolation, super-admin, API keys)
- SQL injection, XSS, CSRF, SSRF, RCE
- Privilege escalation across tenants
- Information disclosure that crosses tenant boundaries
- Cryptographic weaknesses in tokens, sessions, password hashing
- Denial-of-service that bypasses our rate limiters
- Supply-chain risks in our deploy scripts or Odoo plugin

## What we consider out of scope

- Reports requiring physical access to a user's device
- Self-XSS that requires the victim to type code into devtools
- Vulnerabilities in third-party services we depend on (Postgres, Redis,
  Caddy, Next.js) — please report those upstream
- Best-practice nags from automated scanners without a working PoC
- Issues that only affect our public marketing site
- Rate-limit complaints that don't lead to abuse

## Bounty

We don't yet run a formal bounty program. Reports that lead to a fix will
be credited (with permission) in our release notes.

## Hardening you should know about

- **Tenant isolation** — every tenant-scoped table has Postgres Row-Level
  Security; the application sets `app.tenant_id` per-transaction; bypass
  requires explicit `app.bypass_rls = '1'` and only the ADMS receiver +
  super-admin endpoints flip it.
- **Biometrics** — ZKTeco devices may push fingerprint/face templates. Our
  ADMS parser drops `USERPIC`, `FACE`, `FP`, `BIODATA`, `FINGERTMP`,
  `ATTPHOTO` rows BEFORE persisting. We never store biometric templates.
- **Custom-domain SSL** — Caddy on-demand TLS is gated by
  `/api/internal/tls-check`; only domains in `tenant_domains` with status
  `verified|active` get certificates issued.
- **Production guards** — the API refuses to boot if `JWT_SECRET` is short
  / default, if `CORS_ORIGINS` contains `*`, or if `BASE_DOMAIN` looks
  like localhost (see `apps/api/atgo_api/main.py`).

## Configuring a secure deployment

1. Generate `JWT_SECRET` with a CSPRNG (`secrets.token_urlsafe(48)`).
2. Run Postgres on a private network — never expose 5432 publicly.
3. Run the API on `127.0.0.1`, not `0.0.0.0`. Caddy/nginx fronts it.
4. Restrict `admin.atgo.io` to your team's IPs at the edge.
5. Rotate API keys (`atgo_live_*`) when an employee leaves.
6. Set up off-site backups (e.g. WAL streaming + daily `pg_dump` to S3).
