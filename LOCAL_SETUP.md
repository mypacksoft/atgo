# ATGO — Local installation (Windows / macOS / Linux)

End-to-end local stack: Postgres + Redis + FastAPI + Next.js portal + Caddy
(reverse proxy + tenant subdomain routing).

You'll be able to:

- Open the marketing site at `http://atgo.local`
- Sign up at `http://atgo.local/signup`
- Use a tenant workspace at `http://demo.atgo.local`
- Hit the API directly at `http://api.atgo.local`
- Reach the admin UI at `http://admin.atgo.local`
- Simulate ZKTeco device pushes at `http://adms.atgo.local/iclock/...`
- Test the short device URL at `http://atgo.local/{DEVICE_CODE}/iclock/...`

---

## 1. Prerequisites

- **Docker Desktop** (Windows / macOS) or Docker Engine + Compose (Linux),
  v24+ recommended.
- **Python 3** (only if you want to run the device simulator script
  outside Docker).
- Admin / sudo access to edit your `hosts` file.

---

## 2. Edit your hosts file

The tenant routing relies on multiple `*.atgo.local` hostnames. They all
point at 127.0.0.1.

### Windows

1. Open Notepad **as Administrator**.
2. File → Open `C:\Windows\System32\drivers\etc\hosts` (change file
   filter to "All Files").
3. Append these lines:

```
127.0.0.1 atgo.local www.atgo.local
127.0.0.1 api.atgo.local
127.0.0.1 admin.atgo.local
127.0.0.1 adms.atgo.local
127.0.0.1 cname.atgo.local
127.0.0.1 demo.atgo.local
127.0.0.1 abcschool.atgo.local
```

4. Save. (You may need to flush DNS — `ipconfig /flushdns` in cmd.)

### macOS / Linux

```sh
sudo tee -a /etc/hosts <<'EOF'

# ATGO local
127.0.0.1 atgo.local www.atgo.local
127.0.0.1 api.atgo.local
127.0.0.1 admin.atgo.local
127.0.0.1 adms.atgo.local
127.0.0.1 cname.atgo.local
127.0.0.1 demo.atgo.local
127.0.0.1 abcschool.atgo.local
EOF
```

> Need a different tenant slug? Just add another line. The wildcard match
> `*.atgo.local` is handled by Caddy.

---

## 3. Configure environment

```sh
cd D:\ATGO        # (or wherever you cloned the repo)
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
```

Generate a real JWT secret and append it (or paste it into `.env`
manually replacing the placeholder):

```sh
# Windows PowerShell
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))" >> .env
```

```sh
# macOS / Linux
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))" >> .env
```

Then open `.env` and remove the placeholder `JWT_SECRET=change-me…` line
(the appended one wins).

---

## 4. First boot

```sh
docker compose up -d --build
```

This boots **5 containers**: postgres, redis, api, portal, caddy.

Watch them come up:

```sh
docker compose logs -f api      # FastAPI
docker compose logs -f portal   # Next.js
docker compose logs -f caddy    # reverse proxy
```

The first build takes ~3 min (mostly the Next.js portal build).

Health check:

```sh
curl http://api.atgo.local/health
# -> {"ok": true, "env": "development"}
```

---

## 5. End-to-end smoke test

### a) Sign up via the portal UI

1. Open `http://atgo.local/signup`.
2. Fill the form. Pick `demo` as the workspace slug.
3. After submit, you'll land on `http://demo.atgo.local/dashboard`.

### b) Or sign up via curl

```sh
curl -X POST http://api.atgo.local/api/auth/signup ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"owner@demo.com\",\"password\":\"verysecret123\",\"full_name\":\"Demo Owner\",\"company_name\":\"Demo Co\",\"workspace_slug\":\"demo\",\"country\":\"VN\"}"
```

Copy the `access_token` from the response.

### c) Check geo pricing

```sh
curl -H "cf-ipcountry: VN" http://api.atgo.local/api/billing/pricing
```

You should see VND prices via VNPay.

### d) Add a device

In the dashboard go to **Devices → Generate claim code**. You'll get
something like:

```
Device code:  A7K9
Claim code:   A7K9-3F2X
Cloud Server: adms.atgo.local
```

### e) Simulate a ZKTeco push

```sh
python scripts/simulate_zkteco.py --sn TEST-SN-001 --pin 1001 --state 0
```

(or run it in WSL / a Linux VM if your Windows lacks Python).

### f) Confirm the claim from the portal

Back in the dashboard, click **Verify now**. Status flips to `active`.

### g) See the punch land

- Add an employee with PIN `1001` in **Employees**.
- Go to **Attendance** — the simulator's punch is there.
- Go to **Timesheet** for the current month — employee gets a row.
- Click **Download Excel** to grab `timesheet-2026-04.xlsx`.

### h) Connect Odoo (optional)

1. In **API keys**, create a key called "Odoo".
2. Copy the `atgo_live_…` token shown ONCE.
3. In Odoo, install `apps/atgo_connect`.
4. Open **ATGO → Settings**, set Gateway = `http://api.atgo.local`,
   API key = the token. Click **Test connection**.

### i) Employee self-service

1. In **Employees**, click **Invite** on a row that has an email.
2. Copy the invite URL.
3. Open it; set a password; you land on `http://demo.atgo.local/me`
   showing today's punches.

---

## 6. Become a super-admin (for /admin)

The first user is a regular tenant owner — not a super-admin. Promote
yourself with one DB query:

```sh
docker compose exec postgres psql -U atgo -d atgo -c \
  "UPDATE users SET is_super_admin = TRUE WHERE email = 'owner@demo.com';"
```

Then visit `http://admin.atgo.local/admin`.

---

## 7. Common issues

**`http://demo.atgo.local` says workspace not found** — make sure the
hosts entry exists AND the tenant was actually created (signup succeeded).

**Caddy 502 / connection refused** — `docker compose ps` should show
api & portal as `healthy`. If api is restarting, `docker compose logs api`
to see the Python traceback.

**`Cannot find module ...` from Next.js** — re-run
`docker compose build portal && docker compose up -d portal` after
adding npm deps.

**Postgres: relation does not exist** — schema is loaded on first volume
init. If you changed the schema files, wipe and restart:

```sh
docker compose down -v
docker compose up -d --build
```

**Need to log in as employee but no email** — first set the employee's
email in the dashboard (Employees row), then click Invite.

---

## 8. Going to production (cheat-sheet)

1. Set `BASE_DOMAIN=atgo.io` in `.env`.
2. Uncomment the HTTPS blocks in `infra/caddy/Caddyfile`, comment the
   HTTP `*.atgo.local` blocks.
3. Add a Cloudflare API token to `CF_API_TOKEN` for the wildcard cert.
4. Point your domain's A record to the server.
5. Custom domains automatically get certs via on-demand TLS, gated by
   `/api/internal/tls-check`.

---

## 9. Useful commands

```sh
docker compose ps                              # status
docker compose logs -f api portal caddy        # tail multiple
docker compose exec postgres psql -U atgo -d atgo
docker compose exec api python -c "from atgo_api.main import app; print(len(app.routes), 'routes')"
docker compose down                            # stop
docker compose down -v                         # stop + wipe data
```

Enjoy! Open an issue if anything snags.
