# ATGO deployment

## One-shot first deploy

From your Windows machine:

```powershell
pwsh deploy\push_to_server.ps1 `
    -Server   your-server.example.com `
    -Domain   atgo.example.com `
    -RemoteUser root
# (you'll be prompted for the SSH password if no key)
```

That script:
1. tar-balls the local repo (excludes `.venv`, `.pgdata`, `node_modules`, …)
2. scp's tarball + bootstrap to `/tmp/`
3. ssh's in and runs `sudo bash /tmp/bootstrap_server.sh`
4. The bootstrap installs Postgres 16, Redis, Python 3.12, Node 20, Caddy 2, applies schema, builds the portal, writes `/etc/atgo/atgo.env`, and starts the systemd services
5. Pulls the auto-generated deploy private key back to `deploy\atgo_deploy_key`

When done you'll see a banner with super-admin email + password, plus the
URLs (api/admin/adms subdomains).

## DNS to point at the server

```
A      atgo.example.com           <SERVER_IP>
A      *.atgo.example.com         <SERVER_IP>
A      api.atgo.example.com       <SERVER_IP>
A      admin.atgo.example.com     <SERVER_IP>
A      adms.atgo.example.com      <SERVER_IP>
A      cname.atgo.example.com     <SERVER_IP>
```

Caddy will issue Let's Encrypt certs automatically once DNS resolves.

For the `*.atgo.example.com` wildcard you must edit `/etc/caddy/Caddyfile`
and replace `tls internal` with a DNS-01 provider, e.g.:

```caddyfile
*.atgo.example.com {
    tls {
        dns cloudflare {env.CF_API_TOKEN}
    }
    ...
}
```

…then `systemctl reload caddy` after exporting `CF_API_TOKEN` in
`/etc/atgo/atgo.env`.

## Remote ops (Claude Code uses this)

After first deploy, the deploy key lives at `deploy\atgo_deploy_key`. Use:

```bash
deploy/remote.sh systemctl status atgo-api
deploy/remote.sh journalctl -u atgo-api -n 50 --no-pager
deploy/remote.sh sudo -u atgo /opt/atgo/.venv/bin/python -m scripts.bootstrap_admin admin@example.com --password=xxx
```

## Re-deploy code

Re-run the same push command — bootstrap is idempotent, redoes only what
changed (npm build / pip install / restart services):

```powershell
pwsh deploy\push_to_server.ps1 -Server your-server.example.com -Domain atgo.example.com -RemoteUser root
```

For zero-downtime: deploy/remote.sh `cd /opt/atgo/repo && sudo -u atgo bash -c '...'` and
restart only what changed.

## Files

- `bootstrap_server.sh` — runs ON the server. Idempotent.
- `push_to_server.ps1`  — runs on Windows. Pushes code + invokes bootstrap.
- `remote.sh`           — bash wrapper for SSH-and-run-command using the deploy key.
- `atgo_deploy_key`     — private key auto-fetched from server (do NOT commit).
