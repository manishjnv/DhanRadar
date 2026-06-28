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
FAILCOUNT=/var/lib/dhanradar/autodeploy-failcount      # B90: consecutive deploy-failure streak
ALERT_THRESHOLD=3                                       # B90: email after N (~9min) failed polls

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "$(ts) $*" >> "$LOG"; }

# B90 — surface a stalled pipeline instead of failing silently (RCA 2026-06-28: the deploy fail-closed
# on unset DB passwords and nobody noticed for ~24h).
# should_alert: pure predicate, true exactly once per streak (at the threshold) so we don't spam.
should_alert() { [ "${1:-0}" -eq "$ALERT_THRESHOLD" ]; }
# send_failure_alert: best-effort email via Resend. Creds read from .env (gitignored — NEVER in this
# PUBLIC repo). No-ops with a log line if RESEND_API_KEY / ALERT_EMAIL are unset. Never breaks the poll.
send_failure_alert() {
  local n="$1" sha="$2" rc="$3" key to
  key=$(grep -m1 "^RESEND_API_KEY=" .env 2>/dev/null | cut -d= -f2-)
  to=$(grep -m1 "^ALERT_EMAIL=" .env 2>/dev/null | cut -d= -f2-)
  if [ -z "$key" ] || [ -z "$to" ]; then log "alert skipped — RESEND_API_KEY/ALERT_EMAIL unset in .env"; return 0; fi
  if curl -fsS -m 15 -X POST https://api.resend.com/emails \
      -H "Authorization: Bearer ${key}" -H "Content-Type: application/json" \
      -d "{\"from\":\"noreply@dhanradar.com\",\"to\":\"${to}\",\"subject\":\"[DhanRadar] auto-deploy FAILED ${n}x (main@${sha:0:7})\",\"text\":\"deploy.sh failed ${n} consecutive polls deploying main@${sha:0:7} (rc=${rc}); the backend is NOT advancing. Logs on KVM4: /var/log/dhanradar-autodeploy.log + /var/log/dhanradar-manual-deploy.log\"}" \
      >/dev/null 2>>"$LOG"; then log "alert email sent (${n}x failures)"; else log "alert email send FAILED"; fi
}
# selftest: `bash scripts/auto-deploy-poll.sh selftest` — one alert fires per failure streak (no I/O).
run_selftest() {
  local alerts=0 n
  for n in 1 2 3 4 5; do if should_alert "$n"; then alerts=$((alerts+1)); fi; done   # streak 1 -> 1 (at 3)
  for n in 1 2 3;       do if should_alert "$n"; then alerts=$((alerts+1)); fi; done   # streak 2 -> 1 (at 3)
  if [ "$alerts" -eq 2 ]; then echo "selftest OK (alerts=$alerts)"; return 0; else echo "selftest FAIL (alerts=$alerts, want 2)"; return 1; fi
}

if [ "${1:-}" = "selftest" ]; then run_selftest; exit $?; fi

cd "$REPO_DIR"

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
  if bash scripts/deploy.sh deploy >> "$LOG" 2>&1; then
    log "deploy OK -> $(git rev-parse --short HEAD)"
  else
    rc=$?
    n=$(( $(cat "$FAILCOUNT" 2>/dev/null || echo 0) + 1 ))
    mkdir -p "$(dirname "$FAILCOUNT")"; echo "$n" > "$FAILCOUNT"
    log "deploy FAILED (rc=${rc}) ${REMOTE:0:7} — consecutive failures: ${n}"
    if should_alert "$n"; then send_failure_alert "$n" "$REMOTE" "$rc"; fi
    exit 1   # B90: do NOT mark handled — retry next poll (replaces the implicit set -e abort)
  fi
else
  log "${BASE:0:7}->${REMOTE:0:7} docs/ci/scripts-only — fast-forwarded, no rebuild"
fi

# Mark handled ONLY after a fully successful poll; clear the failure streak.
mkdir -p "$(dirname "$MARKER")"
echo "$REMOTE" > "$MARKER"
rm -f "$FAILCOUNT"   # B90: streak broken on any fully-handled poll
