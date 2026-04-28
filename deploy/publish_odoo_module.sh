#!/usr/bin/env bash
# Publish ATGO Connect to its own Git repo with one branch per Odoo version.
#
# Odoo Apps Store wants:
#   - Module folder at the ROOT of the repo
#   - One branch per Odoo series (16.0, 17.0, 18.0, 19.0)
#   - Each branch's manifest version starts with "<series>." e.g. "19.0.0.1.0"
#   - License LGPL-3 (Apache 2.0 not accepted)
#
# This script:
#   1. Creates / updates a clean staging repo at $TARGET_REPO
#   2. For each Odoo version listed, creates a branch with the module
#      folder + manifest tweaked to that series
#   3. Pushes to GitHub (or any remote) if --push is given
#
# Usage:
#   bash deploy/publish_odoo_module.sh                        # build only, no push
#   bash deploy/publish_odoo_module.sh --push                 # push to default remote
#   GITHUB_REMOTE=git@github.com:atgo-io/atgo-odoo-connect.git \
#     bash deploy/publish_odoo_module.sh --push
#
# Requires: git, sed/awk

set -euo pipefail

readonly REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
readonly MODULE_SRC="$REPO_ROOT/apps/atgo_connect"
readonly TARGET_REPO="${TARGET_REPO:-$REPO_ROOT/.publish/atgo-odoo-connect}"
readonly GITHUB_REMOTE="${GITHUB_REMOTE:-git@github.com:atgo-io/atgo-odoo-connect.git}"
readonly ODOO_VERSIONS=("16.0" "17.0" "18.0" "19.0")

PUSH=0
for arg in "$@"; do
    [ "$arg" = "--push" ] && PUSH=1
done

log()  { printf "\033[1;34m▶ %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m! %s\033[0m\n" "$*"; }
ok()   { printf "\033[1;32m✓ %s\033[0m\n" "$*"; }

[ -d "$MODULE_SRC" ] || { warn "module not found at $MODULE_SRC"; exit 1; }

# ---------- 1. clean staging ----------
log "Preparing staging repo at $TARGET_REPO"
rm -rf "$TARGET_REPO"
mkdir -p "$TARGET_REPO"
cd "$TARGET_REPO"
git init -q -b main
git config user.email "release@atgo.io"
git config user.name  "ATGO Release Bot"

# Add a top-level README for browsers landing on github.com/atgo-io/atgo-odoo-connect
cat > README.md <<'README'
# ATGO Connect for Odoo

Free Odoo module that pulls ZKTeco attendance from ATGO Cloud into
`hr.attendance`. No static IP, no port forwarding, no local server required.

## Branches

| Branch | Odoo version |
|--------|--------------|
| `16.0` | Odoo 16.0    |
| `17.0` | Odoo 17.0    |
| `18.0` | Odoo 18.0    |
| `19.0` | Odoo 19.0    |

Pick the branch matching your Odoo version, drop the `atgo_connect/`
folder into your `addons` path, and install from the Apps menu.

For installation steps, configuration, and screenshots see the per-branch
README.rst inside `atgo_connect/`.

License: LGPL-3.
Source of truth: <https://github.com/atgo-io/atgo>.
README

git add README.md
git commit -q -m "init: shared README"

# ---------- 2. one branch per Odoo version ----------
for ver in "${ODOO_VERSIONS[@]}"; do
    log "Building branch $ver"
    git checkout -q -b "$ver" main || git checkout -q "$ver"

    # Copy the module fresh
    rm -rf "atgo_connect"
    cp -R "$MODULE_SRC" "./atgo_connect"

    # Strip __pycache__ + dev artefacts
    find "atgo_connect" -type d -name "__pycache__" -prune -exec rm -rf {} +
    find "atgo_connect" -type f -name "*.pyc" -delete

    # Patch the manifest version to "<ver>.0.1.0"
    # Try in order: $PYTHON env, repo venv, python3, python
    PY_BIN="${PYTHON:-}"
    if [ -z "$PY_BIN" ]; then
        for cand in "$REPO_ROOT/.venv/Scripts/python.exe" "$REPO_ROOT/.venv/bin/python" python3 python; do
            if "$cand" -c "import sys" >/dev/null 2>&1; then
                PY_BIN="$cand"
                break
            fi
        done
    fi
    [ -n "$PY_BIN" ] || { warn "no working python found"; exit 1; }
    "$PY_BIN" - "$ver" "atgo_connect/__manifest__.py" <<'PY'
import ast, re, sys
ver, path = sys.argv[1], sys.argv[2]
with open(path, "r", encoding="utf-8") as f:
    src = f.read()
new_version = f'{ver}.0.1.0'
patched = re.sub(
    r'("version"\s*:\s*)"[^"]+"',
    lambda m: f'{m.group(1)}"{new_version}"',
    src, count=1,
)
with open(path, "w", encoding="utf-8") as f:
    f.write(patched)
print(f"  manifest version -> {new_version}")
PY

    # On Odoo 16, restore the deprecated <tree> tag (Odoo 17+ accepts <list>;
    # Odoo 16 only knows <tree> and view_mode="tree,form").
    if [ "$ver" = "16.0" ]; then
        for f in atgo_connect/views/*.xml; do
            sed -i 's/<list /<tree /g; s|</list>|</tree>|g; s/view_mode">list/view_mode">tree/g' "$f"
        done
    fi

    git add atgo_connect
    if git diff --cached --quiet; then
        warn "no changes for $ver"
    else
        git commit -q -m "release: ATGO Connect for Odoo $ver"
    fi
done

git checkout -q main
ok "staged $TARGET_REPO with branches: ${ODOO_VERSIONS[*]}"

# ---------- 3. optional push ----------
if [ "$PUSH" -eq 1 ]; then
    log "Adding remote $GITHUB_REMOTE"
    git remote remove origin 2>/dev/null || true
    git remote add origin "$GITHUB_REMOTE"
    log "Pushing all branches…"
    git push -u origin main "${ODOO_VERSIONS[@]}" --force-with-lease
    ok "pushed to $GITHUB_REMOTE"
    cat <<DONE

Next steps on apps.odoo.com:
  1. Sign in at https://apps.odoo.com/apps/uploads/new
  2. Repository URL (per Odoo series, submit ONCE for each branch):
     ssh://git@github.com/atgo-io/atgo-odoo-connect.git#19.0
     ssh://git@github.com/atgo-io/atgo-odoo-connect.git#18.0
     ssh://git@github.com/atgo-io/atgo-odoo-connect.git#17.0
     ssh://git@github.com/atgo-io/atgo-odoo-connect.git#16.0
  3. Add the deploy SSH key Odoo gives you to your GitHub repo
     Settings → Deploy keys → Add (read-only is fine).
  4. Wait for review (typically 1–3 business days).

DONE
else
    log "Build complete. Re-run with --push to push to GitHub."
    log "Remote: $GITHUB_REMOTE"
fi
