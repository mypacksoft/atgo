#!/usr/bin/env bash
# Run a command on the ATGO server using the deploy key fetched by
# push_to_server.ps1. Used by Claude Code (Bash tool) for remote ops.
#
# Usage:
#   deploy/remote.sh systemctl status atgo-api
#   deploy/remote.sh journalctl -u atgo-api -n 50 --no-pager
#   deploy/remote.sh psql -U atgo -d atgo -c "SELECT count(*) FROM tenants"

set -euo pipefail

ATGO_SERVER="${ATGO_SERVER:-farm1.mypacksoft.com}"
ATGO_USER="${ATGO_USER:-atgo}"
KEY="${ATGO_KEY:-$(dirname "$0")/atgo_deploy_key}"
PORT="${ATGO_PORT:-22}"

[ -f "$KEY" ] || { echo "deploy key not found at $KEY — run push_to_server.ps1 first" >&2; exit 1; }

ssh -i "$KEY" -p "$PORT" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new \
    "$ATGO_USER@$ATGO_SERVER" "$@"
