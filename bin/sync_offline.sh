#!/bin/bash
#
# Sync this working tree straight to both crosswalk boxes when you're offline.
#
# The normal deploy flow (see README "Deploying new code") has each box
# `git pull` from GitHub over the internet. When you're offline — e.g. wired
# or on Wi-Fi directly to the signs, or on crosswalk-a's "crosswalk" fallback
# AP — that path doesn't work. This script rsyncs your local tree over SSH
# straight into /opt/crosswalk instead, no GitHub involved.
#
# Usage:
#   bin/sync_offline.sh [a|b|all] [--restart] [--dry-run]
#
#   a|b|all     Which box to sync (default: all)
#   --restart   After syncing, restart that box's xwalk_* services
#               (new code isn't live until services are restarted, same as
#               the normal deploy flow)
#   --dry-run   Show what rsync would transfer without changing anything
#
# Env overrides:
#   CROSSWALK_A_HOST  (default: crosswalk-a.local)
#   CROSSWALK_B_HOST  (default: crosswalk-b.local)
#   CROSSWALK_USER    (default: crosswalk, matches ansible_user in inventory.ini)
#   CROSSWALK_DEST    (default: /opt/crosswalk)
#
# If a box isn't reachable (e.g. you're only physically at one sign right
# now), that box is skipped with a warning rather than aborting the whole run.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

A_HOST="${CROSSWALK_A_HOST:-crosswalk-a.local}"
B_HOST="${CROSSWALK_B_HOST:-crosswalk-b.local}"
SSH_USER="${CROSSWALK_USER:-crosswalk}"
DEST="${CROSSWALK_DEST:-/opt/crosswalk}"

usage() {
    grep '^#' "$0" | sed '1d;s/^# \{0,1\}//'
    exit 1
}

TARGET="all"
RESTART=0
DRY_RUN=0

for arg in "$@"; do
    case "$arg" in
        a|b|all) TARGET="$arg" ;;
        --restart) RESTART=1 ;;
        --dry-run) DRY_RUN=1 ;;
        -h|--help) usage ;;
        *)
            echo "Unknown argument: $arg" >&2
            usage
            ;;
    esac
done

# Things a running box doesn't need / shouldn't get overwritten:
#  - .git, caches, nix/venv build artifacts: irrelevant on the box
#  - ansible/private: holds secrets.yaml; never push local secrets over rsync
#  - ansible/.ansible: local ansible runtime state
EXCLUDES=(
    --exclude=/.git/
    --exclude=/.venv/
    --exclude=__pycache__/
    --exclude=/.pytest_cache/
    --exclude=/.direnv/
    --exclude=/.devenv/
    --exclude=/result
    --exclude=/result-*
    --exclude=.DS_Store
    --exclude=/ansible/.ansible/
    --exclude=/ansible/private/
    --exclude=*.egg-info/
)

RSYNC_OPTS=(-az --delete-after --info=progress2)
[[ "$DRY_RUN" -eq 1 ]] && RSYNC_OPTS+=(--dry-run)

host_reachable() {
    ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_USER@$1" true 2>/dev/null
}

sync_host() {
    local host="$1"

    if ! host_reachable "$host"; then
        echo "==> SKIP $host: not reachable over SSH as $SSH_USER" >&2
        return 1
    fi

    echo "==> Syncing $REPO_ROOT/ -> $SSH_USER@$host:$DEST/"
    rsync "${RSYNC_OPTS[@]}" "${EXCLUDES[@]}" "$REPO_ROOT/" "$SSH_USER@$host:$DEST/"

    echo "==> uv sync on $host"
    ssh "$SSH_USER@$host" "cd $DEST && uv sync --no-dev"

    if [[ "$RESTART" -eq 1 && "$DRY_RUN" -eq 0 ]]; then
        echo "==> Restarting xwalk_* services on $host"
        ssh "$SSH_USER@$host" "sudo systemctl restart 'xwalk_*'"
    fi
}

failures=0
case "$TARGET" in
    a) sync_host "$A_HOST" || failures=$((failures + 1)) ;;
    b) sync_host "$B_HOST" || failures=$((failures + 1)) ;;
    all)
        sync_host "$A_HOST" || failures=$((failures + 1))
        sync_host "$B_HOST" || failures=$((failures + 1))
        ;;
esac

echo
if [[ "$RESTART" -ne 1 && "$DRY_RUN" -ne 1 ]]; then
    echo "Note: services were NOT restarted. New code isn't live until:"
    echo "  ssh $SSH_USER@<host> \"sudo systemctl restart 'xwalk_*'\""
fi

if [[ "$failures" -gt 0 ]]; then
    echo "Done with $failures host(s) skipped/failed." >&2
    exit 1
fi
echo "Done."
