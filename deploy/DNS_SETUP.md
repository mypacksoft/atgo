# DNS setup — Dynadot domain `atgo.io`

Two paths. **Pick ONE.**

---

## Path A — Cloudflare-managed DNS (recommended)

You keep the domain registered at Dynadot, but Cloudflare runs the DNS.
This unlocks:
- Free wildcard SSL via DNS-01 challenge in Caddy
- DDoS protection + WAF + global CDN
- Mature API for automating custom-domain provisioning per tenant
- No per-signup DNS API calls needed (wildcard handles all tenants)

### One-time setup

1. **Cloudflare account** → Add site → enter `atgo.io` → Free plan.
2. Cloudflare gives you 2 nameservers, e.g.
   `gemma.ns.cloudflare.com`, `joe.ns.cloudflare.com`.
3. **Dynadot** → My Domains → click `atgo.io` → **Name Servers** →
   choose **Custom** and paste both Cloudflare nameservers → Save.
   (Propagation: 5 min – 24 h, usually < 1 h.)
4. Back in Cloudflare DNS, add records:

   | Type | Name | Value | Proxy |
   |---|---|---|---|
   | A   | atgo.io           | `<SERVER_IP>` | 🟠 proxied |
   | A   | * (wildcard)      | `<SERVER_IP>` | ☁ DNS only (Caddy needs origin for ACME) |
   | A   | api               | `<SERVER_IP>` | 🟠 proxied |
   | A   | admin             | `<SERVER_IP>` | 🟠 proxied |
   | A   | adms              | `<SERVER_IP>` | ☁ DNS only (devices skip CF) |
   | A   | cname             | `<SERVER_IP>` | ☁ DNS only |

5. Cloudflare → My Profile → API Tokens → **Create token** with template
   "Edit zone DNS" scoped to `atgo.io`. Copy the token.
6. Paste in `/etc/atgo/atgo.env` on server:
   ```
   CLOUDFLARE_API_TOKEN=cf_xxxxx
   CLOUDFLARE_ZONE_ID=<from cloudflare dashboard>
   ```
7. Tell Caddy to use Cloudflare for ACME DNS-01 in `/etc/caddy/Caddyfile`:
   ```caddyfile
   *.atgo.io {
       tls {
           dns cloudflare {env.CLOUDFLARE_API_TOKEN}
       }
       ...
   }
   ```
   (Requires the `caddy-dns/cloudflare` plugin — install via `xcaddy build` or
   the Caddy "build a custom binary" page.)

That's it. Every new tenant signup lands on the wildcard automatically.
No per-signup automation needed.

---

## Path B — Dynadot-managed DNS (direct)

Use this only if you want to keep DNS at Dynadot. ATGO will call the
Dynadot API per signup to add `{slug}.atgo.io` as an A record.

### One-time setup

1. **Dynadot** → Tools → API Settings → **Generate API key**. Copy it.
2. Same screen → **IP whitelist** → add your ATGO server's public IPv4.
   (Dynadot rejects calls from non-whitelisted IPs.)
3. Set up the static records manually (Dynadot UI → My Domains → atgo.io
   → DNS):

   | Type | Subdomain | Value |
   |---|---|---|
   | A     | (blank — root) | `<SERVER_IP>` |
   | A     | api            | `<SERVER_IP>` |
   | A     | admin          | `<SERVER_IP>` |
   | A     | adms           | `<SERVER_IP>` |
   | A     | cname          | `<SERVER_IP>` |
   | A     | www            | `<SERVER_IP>` |

   You can also add `*` wildcard here — Dynadot supports it. If you do,
   the per-signup automation is unnecessary. Choose either:

   - **Wildcard at Dynadot** — easy, no per-signup API call. Then in
     `/etc/atgo/atgo.env` leave `DYNADOT_API_KEY` empty.
   - **Per-tenant records via API** — fill `DYNADOT_API_KEY` and the
     server will call `set_dns2` after every signup.

4. In `/etc/atgo/atgo.env`:
   ```
   DYNADOT_API_KEY=<your-api-key>
   DYNADOT_PARENT_DOMAIN=atgo.io
   PUBLIC_IPV4=<server-public-ip>
   ```

### What ATGO does on signup (Path B, per-tenant mode)

`apps/api/atgo_api/routers/auth.py` fires a background task after the
tenant row is committed:

```
asyncio.create_task(_register_subdomain(slug))
   → DynadotClient.add_subdomain_a(slug, server_ipv4)
       → calls https://api.dynadot.com/api3.json?command=set_dns2&...
```

Failures are logged but never block signup. The user lands on
`{slug}.atgo.io` after DNS propagates (usually 5–30 min for Dynadot).

### SSL

Dynadot doesn't have a Caddy DNS plugin, so wildcard SSL via DNS-01 is
not automatic. Options:

- Per-subdomain HTTP-01 (works, but rate-limited by Let's Encrypt to 50
  certs / week / domain — fine for ≤ 7 signups/day on average).
- Manual wildcard cert + reload Caddy.
- Switch to Path A (Cloudflare).

### Why Path A is preferred

| | Cloudflare | Dynadot |
|---|---|---|
| Wildcard DNS-01 SSL | ✅ via Caddy plugin | ❌ manual |
| API rate limit | 1200/5min | tighter |
| API IP allowlist | not required | required |
| Cost | free | free (with Dynadot) |
| DDoS protection | included | none |

---

## Subdomains ATGO uses

| Subdomain | Purpose | Proxy through CF? |
|---|---|---|
| `atgo.io` (root)   | Marketing landing | ✅ |
| `*.atgo.io`        | Tenant workspaces (`{slug}.atgo.io`) | DNS-only (origin must be reachable for SSL) |
| `api.atgo.io`      | Main API | ✅ |
| `admin.atgo.io`    | Internal admin (IP-restrict at Caddy) | ✅ |
| `adms.atgo.io`     | ZKTeco device gateway | DNS-only — many ZK devices break on CF cert chain |
| `cname.atgo.io`    | Target for customer custom-domain CNAMEs | DNS-only |

---

## Troubleshooting

```bash
# resolve check
dig +short api.atgo.io @1.1.1.1
dig +short phuchao.atgo.io @1.1.1.1

# Cloudflare API smoke test
curl -H "Authorization: Bearer $CF_TOKEN" \
     "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID" | jq .success

# Dynadot API smoke test
curl "https://api.dynadot.com/api3.json?key=$DYNADOT_KEY&command=domain_info&domain=atgo.io" | jq .
```
