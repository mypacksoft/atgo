# ATGO — Cloud Attendance for ZKTeco

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-3776ab.svg)](https://www.python.org/)
[![Postgres](https://img.shields.io/badge/postgres-16-336791.svg)](https://www.postgresql.org/)
[![Odoo](https://img.shields.io/badge/odoo-16%20|%2017%20|%2018%20|%2019-714B67.svg)](https://www.odoo.com/)

**Free online attendance system for ZKTeco devices.** No static IP, no port
forwarding, no local server. Multi-tenant SaaS with Odoo HR integration,
custom domains, employee self-service, and geo-aware billing.

> Status: early MVP. Self-hostable. Production-tested foundation but rough
> around the edges in places — read [SECURITY.md](SECURITY.md) before you
> deploy publicly.

## Why

Most ZKTeco attendance setups need a Windows PC with a static IP, port
forwarding on the router, and someone to babysit it. ATGO turns that into a
single config screen on the device pointed at a cloud endpoint — punches
flow into a multi-tenant SaaS that can push them straight to Odoo HR.

## What you get

- **Cloud ADMS receiver** — ZKTeco devices push to a fixed endpoint, no
  network gymnastics required.
- **Multi-tenant portal** — `slug.atgo.io` per workspace, plus custom
  domains via CNAME on Business+ plans.
- **Odoo plugin** — `apps/atgo_connect/` works on Odoo 16, 17, 18, 19. Pulls
  attendance via API key, writes `hr.attendance`, optionally pushes
  `hr.employee` back to ATGO.
- **Employee self-service PWA** — `slug.atgo.io/me` for daily punches,
  monthly timesheet, correction requests, leave.
- **Super-admin portal** — MRR/ARR, tenants, plans, audit log, system
  stats, domain disputes, security events.
- **Geo-aware billing** — VND/VNPay for Vietnam, INR/Razorpay for India,
  USD/Paddle global. Cloudflare `cf-ipcountry` drives auto-selection.
- **Privacy-first** — biometric templates (`USERPIC`, `FACE`, `FP`,
  `BIODATA`, `FINGERTMP`, `ATTPHOTO`) are dropped before persistence. Never
  stored.

## Architecture

```
┌─────────────────┐    HTTPS     ┌──────────────────────────────┐
│ ZKTeco device   │ ───────────► │ adms.atgo.io / atgo.io       │
│ (any model with │              │   FastAPI ADMS receiver      │
│  ADMS support)  │              └────────────┬─────────────────┘
└─────────────────┘                           │
                                              ▼
                            raw_attendance_logs (partitioned monthly)
                                              │
                                              ▼  parse + filter biometrics
                            normalized_attendance_logs (tenant_id, employee_id)
                                              │
              ┌───────────────────────────────┼──────────────────────────┐
              ▼                               ▼                          ▼
   ┌──────────────────┐         ┌──────────────────────────┐   ┌──────────────────┐
   │ Customer portal  │         │ Employee PWA              │   │ Odoo plugin       │
   │ slug.atgo.io     │         │ slug.atgo.io/me           │   │ pulls via API key │
   └──────────────────┘         └──────────────────────────┘   └──────────────────┘
```

Tenant isolation: every workspace-scoped table has Postgres Row-Level
Security. The app sets `app.tenant_id` per transaction. Even if the app
forgets a `WHERE tenant_id =`, the database refuses to leak.

## Stack

- **Backend**: FastAPI · SQLAlchemy 2.0 (async) · asyncpg · Pydantic v2
- **DB**: PostgreSQL 16 with RLS + monthly partitions for log tables
- **Cache / queue**: Redis 7 (rate limit, command queue)
- **Edge / TLS**: Caddy 2 with on-demand TLS for customer custom domains
- **Frontend**: Next.js 15 (App Router) · React 19
- **Odoo plugin**: Python module compatible with 16, 17, 18, 19
- **Containers**: Docker Compose — single-host friendly

## Quick start

```bash
git clone https://github.com/<org>/atgo.git
cd atgo
cp .env.example .env
python -c "import secrets;print('JWT_SECRET=' + secrets.token_urlsafe(48))" >> .env

docker compose up -d --build
docker compose logs -f api
```

Add to your hosts file:

```
127.0.0.1 atgo.local www.atgo.local api.atgo.local
127.0.0.1 admin.atgo.local adms.atgo.local cname.atgo.local
127.0.0.1 demo.atgo.local
```

Smoke test:

```bash
curl http://api.atgo.local/health

# Sign up
curl -X POST http://api.atgo.local/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"owner@demo.com","password":"verysecret123",
       "full_name":"Demo Owner","company_name":"Demo Co",
       "workspace_slug":"acme","country":"VN"}'

# Simulate a device
python scripts/simulate_zkteco.py --sn TEST-SN-001 --pin 1001 --state 0
```

For deployment to a real server see [`deploy/README.md`](deploy/README.md).

## Pricing model (defaults)

| Plan       | USD / mo | Devices  | Custom domain | Log retention |
|------------|---------:|---------:|---------------|---------------|
| Free       |       $0 |        1 | —             | 30 days       |
| Starter    |       $9 |        3 | —             | 60 days       |
| Business   |      $29 |       10 | 1             | 180 days      |
| Scale      |      $49 |       25 | 3             | 365 days      |
| HR Pro     |      $79 |       25 | 5 + auto-DNS  | 365 days      |

Localized pricing for VN (VND), IN (INR), and others — see
`apps/api/atgo_api/constants.py:PRICING_MATRIX`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). For security issues see
[SECURITY.md](SECURITY.md).

## License

[Apache License 2.0](LICENSE).
