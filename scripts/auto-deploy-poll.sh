#!/usr/bin/env bash
# =============================================================================
# scripts/auto-deploy-poll.sh — pull-based auto-deploy for KVM4.
#
# Runs from /opt/dhanradar via a host cron under flock. Deploys origin/main when
# it advances AND its CI is green, UNLESS the change is docs / ci / scripts-only.
#
# WHY pull-based (not a GitHub Action that pushes to the box): KVM4 is a shared
# box that also runs the SSH-lifeline tunnel + other live projects, and this repo
# is PUBLIC. A self-hosted runner or an inbound SSH route would expose the lifeline
# box to fork-PR risk. This poller needs NO inbound access, NO secrets, NO
# cloudflared change, NO persistent runner — it only reaches OUT to git + the
# public GitHub API. Secure by construction.
#
# SAFETY: anything on main has already passed CI, and this script re-verifies the
# required check-runs are green on the exact target commit BEFORE building. A
# failed deploy aborts before the success marker is written, so the next poll
# retries. Idempotent: no new commit -> no-op; docs-only -> fast-forward, no rebuild.
#
# Disable: comment out the `dhanradar-autodeploy` cron line (crontab -e). Logs:
# /var/log/dhanradar-autodeploy.log. Last-deployed marker: the MARKER path below.
# =============================================================================
set -euo pipefail

REPO_DIR=/opt/dhanradar
GH_REPO="manishjnv/DhanRadar"
REQUIRED_CHECKS="guards backend migrations frontend"   # blocking CI jobs (not advisory lint)
MARKER=/var/lib/dhanradar/last-deployed-sha
LOG=/var/log/dhanradar-autodeploy.log

cd "$REPO_DIR"
ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "$(ts) $*" >> "$LOG"; }

git fetch origin main --quiet
REMOTE=$(git rev-parse origin/main)
LAST=$(cat "$MARKER" 2>/dev/null || echo "")
[ "$LAST" = "$REMOTE" ] && exit 0   # this commit already handled — no-op

# --- Gate on CI: deploy only a commit whose REQUIRED checks are all green. -----
# Public repo -> the check-runs API is readable unauthenticated. We only call it
# when main has advanced, so well under the 60/hr unauth rate limit.
CONCLUSION=$(curl -fsSL -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${GH_REPO}/commits/${REMOTE}/check-runs?per_page=100" 2>/dev/null \
  | python3 -c "
import sys, json
req = set('${REQUIRED_CHECKS}'.split())
try:
    runs = {r['name']: (r.get('conclusion') or 'pending') for r in json.load(sys.stdin).get('check_runs', [])}
except Exception:
    print('error'); sys.exit()
if any(c not in runs or runs[c] == 'pending' for c in req):
    print('pending')
elif all(runs[c] == 'success' for c in req):
    print('success')
else:
    print('failed')
" 2>/dev/null || echo "error")

if [ "$CONCLUSION" != "success" ]; then
  log "main@${REMOTE:0:7} CI=${CONCLUSION} — holding (no deploy)"
  exit 0
fi

# --- Advance the checkout to the CI-green main. --------------------------------
PREV=$(git rev-parse HEAD)
git checkout main --quiet
git pull --ff-only origin main >> "$LOG" 2>&1

# --- Deploy only when a RUNTIME path changed since the last handled commit. ----
BASE="${LAST:-$PREV}"
CHANGED=$(git diff --name-only "$BASE" "$REMOTE" 2>/dev/null || echo "__ALL__")
if [ "$CHANGED" = "__ALL__" ] || \
   printf '%s\n' "$CHANGED" | grep -qvE '^(docs/|\.github/|\.claude/|scripts/|.*\.md$)'; then
  log "deploy ${BASE:0:7}->${REMOTE:0:7} (runtime change, CI green)"
  bash scripts/deploy.sh deploy >> "$LOG" 2>&1
  log "deploy OK -> $(git rev-parse --short HEAD)"
else
  log "${BASE:0:7}->${REMOTE:0:7} docs/ci/scripts-only — fast-forwarded, no rebuild"
fi

# Mark handled ONLY after success. `set -e` aborts before here if deploy.sh failed,
# so a transient failure is retried on the next poll.
mkdir -p "$(dirname "$MARKER")"
echo "$REMOTE" > "$MARKER"
