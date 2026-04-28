# Contributing to ATGO

Thanks for your interest! This guide covers the practical bits.

## Quick start

```bash
git clone https://github.com/<org>/atgo.git
cd atgo
cp .env.example .env
# Generate a JWT secret
python -c "import secrets;print('JWT_SECRET=' + secrets.token_urlsafe(48))" >> .env
docker compose up -d --build
```

See [`LOCAL_SETUP.md`](LOCAL_SETUP.md) for a step-by-step that doesn't use
Docker.

## Project layout

```
apps/
  api/              FastAPI + SQLAlchemy + asyncpg
  portal/           Next.js 15 (App Router) — landing, dashboard, admin
  atgo_connect/     Odoo 16/17/18/19 module (LGPL-3, separate Apps Store repo)
infra/
  postgres/         init.sql + feature migrations (RLS, partitions)
  caddy/            Caddyfile — dev + production
deploy/             Server bootstrap + remote ops
scripts/            Helpers (ZKTeco simulator, hosts sync)
```

## Running tests

```bash
cd apps/api
python -m pytest -q
```

## Code style

- **Python**: ruff, type hints required, async-first.
- **TypeScript**: strict mode, no `any` unless necessary.
- **SQL**: prefer parameterized queries (`text(":x")`); never f-string user input.

Run `ruff check apps/api/atgo_api/` before sending a PR.

## Pull requests

- One PR per feature / fix.
- Describe the **why**, not just the what.
- Include tests for non-trivial logic (RLS bypass risks, payment flows, ADMS edge cases).
- For UI changes, include a screenshot or short loom.
- Don't hand-edit migrations once merged — add a new file.

## Sensitive areas — please loop in a maintainer first

- Tenant isolation / RLS (`db.py`, `deps.py`, policies in `init.sql`)
- ADMS receiver (`routers/adms.py`) — protocol semantics matter
- Billing / webhooks (`routers/billing.py`, `services/billing_verify.py`)
- Auth flows (`routers/auth.py`, `security.py`)

## Reporting bugs

Open an issue with:
- ATGO version (commit hash)
- ZKTeco device model + firmware (if relevant)
- Steps to reproduce
- Expected vs actual

For security issues see [SECURITY.md](SECURITY.md) — please don't file public issues.

## License

By contributing you agree your code is released under the [Apache 2.0 license](LICENSE).
