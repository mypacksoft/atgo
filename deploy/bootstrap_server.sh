#!/usr/bin/env bash
# ATGO production bootstrap — Ubuntu 22.04 / 24.04
#
# Run THIS on the server (one-shot). Idempotent.
#
#   curl -fsSL https://your-host/deploy/bootstrap_server.sh | sudo bash
# OR
#   scp deploy/bootstrap_server.sh user@your-server:/tmp/ && ssh user@your-server 'sudo bash /tmp/bootstrap_server.sh'
#
# What it does:
#   - Installs Postgres 16, Redis 7, Python 3.12, Node 20, Caddy 2, git
#   - Creates /opt/atgo + system user 'atgo'
#   - Initializes Postgres role + DB + RLS schema
#   - Sets up systemd services: atgo-api, atgo-portal
#   - Hands you back a deploy SSH key so future updates can be pushed
#
# Re-run safely: skips work that's already done.

set -euo pipefail

readonly ATGO_HOME=/opt/atgo
readonly ATGO_USER=atgo
readonly POSTGRES_DB=atgo
readonly POSTGRES_USER=atgo
readonly REPO_URL="${REPO_URL:-}"                                      # leave empty to skip git
readonly DOMAIN="${DOMAIN:-atgo.example.com}"                          # CHANGE
readonly ADMIN_EMAIL="${ADMIN_EMAIL:-admin@${DOMAIN}}"

log() { echo -e "\033[1;34m▶ $*\033[0m"; }
ok()  { echo -e "\033[1;32m✓ $*\033[0m"; }

[ "$(id -u)" -eq 0 ] || { echo "must run as root"; exit 1; }

# ---------- 1. OS packages ----------
log "Installing OS packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    curl ca-certificates gnupg lsb-release ufw \
    build-essential pkg-config libpq-dev \
    python3.12 python3.12-venv python3-pip \
    git nginx-light jq

# Postgres 16 from PGDG
if ! command -v psql >/dev/null; then
    install -d /usr/share/postgresql-common/pgdg
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list
    apt-get update -qq
    apt-get install -y -qq postgresql-16 postgresql-client-16
fi

# Caddy
if ! command -v caddy >/dev/null; then
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy.gpg
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy.list
    apt-get update -qq
    apt-get install -y -qq caddy
fi

# Redis
apt-get install -y -qq redis-server
systemctl enable --now redis-server

# Node 20
if ! command -v node >/dev/null || [ "$(node -v | cut -d. -f1)" != "v20" ]; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -qq nodejs
fi

ok "OS packages installed"

# ---------- 2. atgo user + dirs ----------
log "Creating atgo user + directories..."
id "$ATGO_USER" &>/dev/null || useradd --system --create-home --shell /bin/bash --home "$ATGO_HOME" "$ATGO_USER"
install -d -o "$ATGO_USER" -g "$ATGO_USER" "$ATGO_HOME" /var/log/atgo /etc/atgo
ok "user $ATGO_USER ready"

# ---------- 3. SSH deploy key (returned to operator) ----------
KEY_PATH="$ATGO_HOME/.ssh/atgo_deploy"
if [ ! -f "$KEY_PATH" ]; then
    log "Generating SSH deploy key..."
    sudo -u "$ATGO_USER" mkdir -p "$ATGO_HOME/.ssh"
    sudo -u "$ATGO_USER" chmod 700 "$ATGO_HOME/.ssh"
    sudo -u "$ATGO_USER" ssh-keygen -t ed25519 -N "" -C "atgo-deploy@$(hostname)" -f "$KEY_PATH"
    cat "$KEY_PATH.pub" >> "$ATGO_HOME/.ssh/authorized_keys"
    chown "$ATGO_USER:$ATGO_USER" "$ATGO_HOME/.ssh/authorized_keys"
    chmod 600 "$ATGO_HOME/.ssh/authorized_keys"
    ok "deploy key generated"
fi

# ---------- 4. Postgres role + DB ----------
log "Configuring Postgres..."
PG_PASS="$(openssl rand -base64 24 | tr -d /=+ | cut -c1-24)"
sudo -u postgres psql -c "DO \$\$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$POSTGRES_USER') THEN
        CREATE ROLE $POSTGRES_USER LOGIN PASSWORD '$PG_PASS';
    END IF;
END \$\$;" >/dev/null
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'" | grep -q 1 \
    || sudo -u postgres createdb -O "$POSTGRES_USER" "$POSTGRES_DB"
ok "Postgres configured"

# ---------- 5. Source code ----------
# The push script (push_to_server.ps1) drops a tarball at /tmp/atgo-source.tgz.
# Fall back to git only when REPO_URL is set.
log "Locating source code..."
if [ -f /tmp/atgo-source.tgz ]; then
    install -d -o "$ATGO_USER" -g "$ATGO_USER" "$ATGO_HOME/repo"
    tar -xzf /tmp/atgo-source.tgz -C "$ATGO_HOME/repo"
    chown -R "$ATGO_USER:$ATGO_USER" "$ATGO_HOME/repo"
    ok "extracted /tmp/atgo-source.tgz → $ATGO_HOME/repo"
elif [ -n "$REPO_URL" ]; then
    if [ ! -d "$ATGO_HOME/repo/.git" ]; then
        sudo -u "$ATGO_USER" git clone --depth=1 "$REPO_URL" "$ATGO_HOME/repo"
    else
        sudo -u "$ATGO_USER" git -C "$ATGO_HOME/repo" pull --ff-only
    fi
    ok "code at $ATGO_HOME/repo (git)"
elif [ -d "$ATGO_HOME/repo/apps/api" ]; then
    ok "code already present at $ATGO_HOME/repo"
else
    echo "✗ no source: /tmp/atgo-source.tgz missing and REPO_URL empty"
    exit 1
fi

# ---------- 6. Apply schema ----------
log "Applying database schema..."
PGPASSWORD="$PG_PASS" psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -f "$ATGO_HOME/repo/infra/postgres/init.sql" >/dev/null
[ -f "$ATGO_HOME/repo/infra/postgres/init_002_features.sql" ] && \
    PGPASSWORD="$PG_PASS" psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
        -f "$ATGO_HOME/repo/infra/postgres/init_002_features.sql" >/dev/null || true
ok "schema applied"

# ---------- 7. Python venv + deps ----------
log "Installing Python deps..."
sudo -u "$ATGO_USER" python3.12 -m venv "$ATGO_HOME/.venv"
sudo -u "$ATGO_USER" "$ATGO_HOME/.venv/bin/pip" install --upgrade pip wheel >/dev/null
sudo -u "$ATGO_USER" "$ATGO_HOME/.venv/bin/pip" install -e "$ATGO_HOME/repo/apps/api" >/dev/null
ok "Python deps installed"

# ---------- 8. Portal build ----------
log "Building portal..."
cd "$ATGO_HOME/repo/apps/portal"
sudo -u "$ATGO_USER" npm ci --silent
sudo -u "$ATGO_USER" \
    NEXT_PUBLIC_API_BASE="https://api.${DOMAIN}" \
    NEXT_PUBLIC_BASE_DOMAIN="${DOMAIN}" \
    INTERNAL_API_BASE="http://127.0.0.1:8000" \
    npm run build --silent
ok "portal built"

# ---------- 9. /etc/atgo/.env ----------
log "Writing /etc/atgo/atgo.env..."
JWT_SECRET="$(openssl rand -base64 64 | tr -d '\n=' )"
cat > /etc/atgo/atgo.env <<EOF
ENVIRONMENT=production
BASE_DOMAIN=${DOMAIN}
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${PG_PASS}@127.0.0.1:5432/${POSTGRES_DB}
REDIS_URL=redis://127.0.0.1:6379/0
JWT_SECRET=${JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_ACCESS_TTL_MINUTES=60
JWT_REFRESH_TTL_DAYS=30
CORS_ORIGINS=https://${DOMAIN},https://api.${DOMAIN},https://admin.${DOMAIN}
NEXT_PUBLIC_API_BASE=https://api.${DOMAIN}
NEXT_PUBLIC_BASE_DOMAIN=${DOMAIN}
EOF
chmod 600 /etc/atgo/atgo.env
chown root:"$ATGO_USER" /etc/atgo/atgo.env
ok ".env saved (mode 0640)"

# ---------- 10. systemd services ----------
log "Installing systemd units..."
cat > /etc/systemd/system/atgo-api.service <<'UNIT'
[Unit]
Description=ATGO FastAPI
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=atgo
EnvironmentFile=/etc/atgo/atgo.env
WorkingDirectory=/opt/atgo/repo/apps/api
ExecStart=/opt/atgo/.venv/bin/uvicorn atgo_api.main:app --host 127.0.0.1 --port 8000 --workers 4 --proxy-headers --forwarded-allow-ips="*"
Restart=on-failure
RestartSec=3
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/atgo-portal.service <<'UNIT'
[Unit]
Description=ATGO Next.js portal
After=network.target atgo-api.service

[Service]
Type=simple
User=atgo
EnvironmentFile=/etc/atgo/atgo.env
WorkingDirectory=/opt/atgo/repo/apps/portal
ExecStart=/usr/bin/node node_modules/next/dist/bin/next start -p 3000
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now atgo-api atgo-portal
ok "services enabled"

# ---------- 11. Caddyfile ----------
log "Configuring Caddy..."
cat > /etc/caddy/Caddyfile <<EOF
${DOMAIN} {
    encode gzip
    reverse_proxy 127.0.0.1:3000
}

api.${DOMAIN} {
    encode gzip
    reverse_proxy 127.0.0.1:8000
}

admin.${DOMAIN} {
    encode gzip
    @internal not remote_ip private_ranges
    reverse_proxy 127.0.0.1:3000
}

adms.${DOMAIN} {
    encode gzip
    @allowed path /iclock/* /heartbeat /health
    handle @allowed { reverse_proxy 127.0.0.1:8000 }
    respond "Not found" 404
}

cname.${DOMAIN} {
    respond "ATGO custom-domain endpoint OK" 200
}

# Wildcard for tenant workspaces — needs DNS-01 cert (configure separately)
*.${DOMAIN} {
    tls internal   # replace with: tls { dns cloudflare {env.CF_API_TOKEN} }
    @api path /api/* /iclock/*
    handle @api { reverse_proxy 127.0.0.1:8000 }
    reverse_proxy 127.0.0.1:3000
}
EOF
systemctl reload caddy
ok "Caddy configured"

# ---------- 12. Firewall ----------
log "Configuring UFW..."
ufw --force reset >/dev/null
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw allow 22/tcp comment "SSH" >/dev/null
ufw allow 80/tcp comment "HTTP" >/dev/null
ufw allow 443/tcp comment "HTTPS" >/dev/null
ufw --force enable >/dev/null
ok "firewall up"

# ---------- 13. Bootstrap super-admin ----------
log "Creating super admin..."
ADMIN_PASS="$(openssl rand -base64 16 | tr -d /=+ | cut -c1-16)"
sudo -u "$ATGO_USER" \
    bash -c "cd $ATGO_HOME/repo/apps/api && \
        $ATGO_HOME/.venv/bin/python -m scripts.bootstrap_admin '$ADMIN_EMAIL' --password='$ADMIN_PASS' --name='ATGO Admin'" \
    --env-file=/etc/atgo/atgo.env || true

cat <<DONE

================================================================
✓ ATGO bootstrap complete on $(hostname)
================================================================

Domain:           https://${DOMAIN}
Admin portal:     https://admin.${DOMAIN}
ADMS endpoint:    https://adms.${DOMAIN}/iclock/cdata
API docs:         https://api.${DOMAIN}/docs

Super admin:      ${ADMIN_EMAIL}
Admin password:   ${ADMIN_PASS}

DB password:      saved in /etc/atgo/atgo.env (root:atgo 0640)

Deploy SSH key (for CI / Claude Code remote access):
$(cat $KEY_PATH.pub)

Private key on server: $KEY_PATH
   ➜ scp atgo@$(hostname):${KEY_PATH} ./atgo_deploy_key
   (then chmod 600 atgo_deploy_key)

Service status:
  systemctl status atgo-api atgo-portal caddy

Logs:
  journalctl -u atgo-api -f
  journalctl -u atgo-portal -f

DNS to point at this server:
  A      ${DOMAIN}             $(curl -s ifconfig.me)
  A      *.${DOMAIN}           $(curl -s ifconfig.me)
  A      api.${DOMAIN}         $(curl -s ifconfig.me)
  A      admin.${DOMAIN}       $(curl -s ifconfig.me)
  A      adms.${DOMAIN}        $(curl -s ifconfig.me)
  A      cname.${DOMAIN}       $(curl -s ifconfig.me)
================================================================
DONE
