# Pre-publish risk audit — ATGO

Performed before first GitHub push.

## Summary

| Status | Item |
|:---:|---|
| ✅ | No secrets, keys, or `.env` files staged |
| ✅ | `.pgdata/`, `.venv/`, `node_modules/`, `.next/`, `.publish/` excluded |
| ✅ | Personal info (`farm1.mypacksoft.com`, real IPs) sanitized to `your-server.example.com` |
| ✅ | Production guard rails (refuse to boot with default `JWT_SECRET`, wildcard CORS, `localhost` BASE_DOMAIN) |
| ✅ | All raw SQL uses parameterized binds; column lists in dynamic UPDATEs come from Pydantic-validated whitelists |
| ✅ | RLS policies enabled + forced on every tenant-scoped table |
| ✅ | Biometric data (`USERPIC` / `FACE` / `FP` / `BIODATA` / `FINGERTMP` / `ATTPHOTO`) dropped at ADMS edge |
| ✅ | Caddy on-demand TLS gated by `/api/internal/tls-check` (rejects unknown domains → no free SSL farm) |
| ✅ | Odoo module licensed LGPL-3 (Apache 2.0 not accepted by Odoo Apps); main repo Apache 2.0 |
| ⚠ | Banner image for Odoo Apps listing not yet present (`static/description/banner.png`) |
| ⚠ | Default JWT secret in `config.py` is `"dev-secret-change-me"` — fine for dev, refused at startup in prod |
| ⚠ | Webhook signature verification: VNPay / Razorpay implementations exist but NOT exercised by tests |
| ⚠ | No automated test suite yet — recommend smoke-test workflow on push |

## Repo composition

```
129 files total
  ├─ 107  apps/         (FastAPI + Next.js portal + Odoo connector)
  ├─    7 deploy/       (server bootstrap, GH publish, Odoo Apps split)
  ├─    4 infra/        (Postgres init.sql, Caddy)
  ├─    3 scripts/      (ZK simulator, hosts sync)
  └─    8 root          (LICENSE, README, SECURITY, CONTRIBUTING, .env.example, …)

Code volume:
  Python:        6,177 LOC
  TypeScript:    3,656 LOC
  SQL:             725 LOC
```

## What's NOT in the repo (gitignored, verified)

- `.env`, `.env.local`, `.env.production`
- `.pgdata/` (local Postgres cluster)
- `.venv/`, `apps/portal/node_modules/`, `apps/portal/.next/`
- `deploy/atgo_deploy_key`, `deploy/atgo_deploy_key.pub`
- `.publish/` (Odoo Apps build output)
- `*.atgo-backup-*` (Windows hosts file backups)

## Known surface for follow-up

| Area | Risk | Mitigation needed |
|---|---|---|
| Webhook signatures | Medium | Add tests forging valid + invalid signatures per provider |
| ADMS auth | Medium | HMAC shared key path defined in schema; not yet enforced for active devices |
| Rate-limit fail-open | Low | Documented; only kicks in when Redis unreachable |
| ADMS UNKNOWN payload sink | Low | Unknown SN logs go to `tenant_id=0` raw bucket; rotate-cleanup needed |
| Custom-domain takeover | Low | `tenant_domains` partial unique index on pending/active prevents claim collisions |
| Postgres exposure | High if misconfigured | Bootstrap binds to 127.0.0.1; UFW blocks 5432 by default; document this |
| Super-admin password | Medium | `bootstrap_admin.py` requires `--password`; recommend `pass` rotation policy |

## Publish steps (in order)

1. **Final review**: `git diff --cached --stat | head -50` — eyeball
2. **Push main repo**:
   ```
   bash deploy/publish_github.sh atgo-io --public --push
   ```
3. **Odoo Apps Store**:
   ```
   bash deploy/publish_odoo_module.sh --push
   ```
   Then submit each branch (16.0/17.0/18.0/19.0) at apps.odoo.com.
   Add the deploy SSH key Odoo provides to the GitHub repo Settings → Deploy keys.
4. **Add GitHub repo metadata** (topics, description, homepage):
   ```
   gh repo edit atgo-io/atgo \
     --add-topic saas --add-topic zkteco --add-topic odoo \
     --add-topic attendance --add-topic fastapi --add-topic nextjs \
     --homepage https://atgo.io
   ```
5. **Enable security advisories**:
   ```
   gh repo edit atgo-io/atgo --enable-security-and-analysis
   ```
6. **Set up branch protection** for `main` after first push.

## Things to add post-publish

- [ ] CI workflow: `pytest`, `ruff`, `next build`
- [ ] Dependabot for npm + pip
- [ ] CodeQL scanner
- [ ] `CHANGELOG.md`
- [ ] Issue + PR templates
- [ ] `static/description/banner.png` (1280×480) for Odoo Apps listing
- [ ] Real banner / favicon assets (currently placeholders)
- [ ] Webhook signature verification tests
