#!/usr/bin/env bash
# Publish ATGO main repo to GitHub.
#
# Prerequisites:
#   - `gh` CLI installed (https://cli.github.com/) and authenticated
#     (`gh auth login` with a personal-access token having `repo` scope)
#   - You're sitting in the project root
#
# Examples:
#   bash deploy/publish_github.sh                          # dry-run audit only
#   bash deploy/publish_github.sh atgo-io                  # create under org `atgo-io`
#   bash deploy/publish_github.sh atgo-io --private        # private repo
#   bash deploy/publish_github.sh atgo-io --public --push  # public + push
#
# Audit before push:
#   - .env / .env.local / *.atgo-backup-* / .pgdata / deploy/atgo_deploy_key
#     must NOT show up in `git ls-files`
#   - Files larger than 1 MB are flagged

set -euo pipefail

readonly REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
readonly REPO_NAME="atgo"

ORG="${1:-}"
VISIBILITY="--private"
DO_PUSH=0
shift || true
for arg in "$@"; do
    case "$arg" in
        --public)  VISIBILITY="--public" ;;
        --private) VISIBILITY="--private" ;;
        --push)    DO_PUSH=1 ;;
    esac
done

log()  { printf "\033[1;34m▶ %s\033[0m\n" "$*"; }
ok()   { printf "\033[1;32m✓ %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m! %s\033[0m\n" "$*"; }
err()  { printf "\033[1;31m✗ %s\033[0m\n" "$*" >&2; }

cd "$REPO_ROOT"

# ---------- 1. Init git if missing ----------
if [ ! -d .git ]; then
    log "Initializing git repository"
    git init -q -b main
    git config user.email "release@atgo.io"
    git config user.name  "ATGO"
fi

# ---------- 2. Stage everything respecting .gitignore ----------
log "Staging files"
git add -A

# ---------- 3. Audit before commit ----------
log "Auditing staged tree for sensitive files"
declare -i issues=0

check() {
    local label="$1" reason="$2" pattern="$3"
    local matches
    matches="$(git ls-files | grep -E "$pattern" | grep -v -E "(\.example|\.sample|\.template)$" || true)"
    if [ -n "$matches" ]; then
        err "  STAGED: $label — $reason"
        echo "$matches" | sed 's/^/      /'
        issues=$((issues + 1))
    fi
}

check ".env"              "contains JWT secret + DB password" '(^|/)\.env$'
check ".env.local"        "contains local secrets"            '(^|/)\.env\.[a-z]+$'
check ".pgdata/"          "local Postgres cluster data"       '(^|/)\.pgdata(/|$)'
check "atgo_deploy_key"   "server SSH private key"            'atgo_deploy_key(\.pub)?$'
check "*.tgz / *.tar.gz"  "deployment artefact"               '\.(tgz|tar\.gz)$'
check "venv directories"  "Python virtualenv leaked"          '(^|/)(\.venv|venv|env)/'
check "node_modules"      "JS deps leaked"                    '(^|/)node_modules/'
check ".pyc / __pycache__" "compiled Python"                  '(\.pyc$|__pycache__/)'
check "id_rsa / id_ed25519" "SSH private key"                 '(^|/)(id_rsa|id_ed25519)(\.pub)?$'

# Files >1MB
big=$(git ls-files | xargs -I {} sh -c 'sz=$(wc -c < "{}" 2>/dev/null || echo 0); [ "$sz" -gt 1048576 ] && echo "$sz  {}"' 2>/dev/null | sort -nr | head -10 || true)
if [ -n "$big" ]; then
    warn "Files >1 MB staged (review):"
    echo "$big" | sed 's/^/    /'
fi

# Hardcoded high-entropy strings outside .env.example
suspicious=$(git ls-files | grep -v "\.env\.example$\|README\|\.md$\|LICENSE\|\.lock$" \
    | xargs grep -l -E 'sk_live_|pk_live_|atgo_live_[a-zA-Z0-9]{20}|JWT_SECRET=[A-Za-z0-9_-]{30,}' 2>/dev/null | head -5 || true)
if [ -n "$suspicious" ]; then
    warn "Possible hardcoded keys (review manually):"
    echo "$suspicious" | sed 's/^/    /'
fi

if [ $issues -gt 0 ]; then
    err "$issues sensitive file(s) staged. Update .gitignore and re-run."
    exit 1
fi
ok "audit passed"

# ---------- 4. Optional: dry run ends here ----------
if [ -z "$ORG" ]; then
    log "Dry-run mode (no org argument). Stop here."
    log "Re-run with: bash deploy/publish_github.sh <org> --public --push"
    exit 0
fi

# ---------- 5. Commit if needed ----------
if ! git diff --cached --quiet || [ -z "$(git log -1 --oneline 2>/dev/null)" ]; then
    log "Committing"
    git commit -q -m "init: ATGO platform — FastAPI + Next.js + Postgres + Odoo connect

- Multi-tenant SaaS with Postgres RLS isolation
- ZKTeco ADMS receiver + claim flow (HMAC-ready)
- Customer + super-admin portals (Next.js 15)
- Odoo 16/17/18/19 connector (LGPL-3, separate Apps Store repo)
- Geo-aware billing (Paddle / VNPay / Razorpay)
- Custom-domain CNAME via Caddy on-demand TLS"
fi

# ---------- 6. Create GitHub repo ----------
if ! command -v gh >/dev/null; then
    err "gh CLI not found. Install: https://cli.github.com/"
    exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
    err "gh CLI not authenticated. Run: gh auth login"
    exit 1
fi

FULL_REPO="$ORG/$REPO_NAME"
if gh repo view "$FULL_REPO" >/dev/null 2>&1; then
    ok "GitHub repo $FULL_REPO already exists"
else
    log "Creating $FULL_REPO ($VISIBILITY)"
    gh repo create "$FULL_REPO" $VISIBILITY \
        --description "Cloud Attendance for ZKTeco — FastAPI + Next.js + Postgres + Odoo. Multi-tenant SaaS, custom domains, biometric-safe." \
        --source . \
        --remote origin
fi

# ---------- 7. Push ----------
if [ $DO_PUSH -eq 1 ]; then
    log "Pushing to origin/main"
    git push -u origin main
    ok "pushed to https://github.com/$FULL_REPO"
else
    warn "skipping push (use --push to upload)"
fi

cat <<DONE

Repo:     https://github.com/$FULL_REPO
Topics:   gh repo edit $FULL_REPO --add-topic saas,zkteco,odoo,attendance,fastapi,nextjs,postgres
Settings: gh repo edit $FULL_REPO --enable-issues --enable-discussions

For the Odoo Apps store, also publish the connector:
  bash deploy/publish_odoo_module.sh --push
DONE
