#!/usr/bin/env bash
# scripts/rollback.sh — Roll back DhanRadar to the last recorded good state.
# Runs on the Linux host; must be executed from the repo root.
# Usage: bash scripts/rollback.sh [target-git-sha [target-alembic-rev]]
#   $1 — optional: target git SHA (overrides .deploy/last-good-sha)
#   $2 — optional: target alembic revision (overrides .deploy/last-good-alembic)
#   CONFIRM_DB_DOWNGRADE=1 — required to actually run alembic downgrade
set -euo pipefail

DEPLOY_DIR=".deploy"
TIMESTAMP() { date '+%Y-%m-%dT%H:%M:%S'; }
log() { echo "[$(TIMESTAMP)] $*"; }
die() { echo "[$(TIMESTAMP)] ERROR: $*" >&2; exit 1; }
warn() { echo "[$(TIMESTAMP)] WARNING: $*" >&2; }

# ── 1. Preconditions ──────────────────────────────────────────────────────────
log "=== DhanRadar rollback started ==="

[[ -f "docker-compose.yml" ]] \
  || die "docker-compose.yml not found. Run from the repo root."

[[ -f ".env" ]] \
  || die ".env not found at repo root. Secrets file is required."

docker compose version > /dev/null 2>&1 \
  || die "docker compose (v2) is not available."

# ── 2. Resolve rollback targets ───────────────────────────────────────────────
if [[ -n "${1:-}" ]]; then
  TARGET_SHA="${1}"
  log "Using provided target SHA: ${TARGET_SHA}"
else
  [[ -f "${DEPLOY_DIR}/last-good-sha" ]] \
    || die "${DEPLOY_DIR}/last-good-sha not found. Run a successful deploy first, or pass a target SHA as \$1."
  TARGET_SHA="$(cat "${DEPLOY_DIR}/last-good-sha")"
  log "Using recorded last-good SHA: ${TARGET_SHA}"
fi

if [[ -n "${2:-}" ]]; then
  TARGET_ALEMBIC="${2}"
  log "Using provided target alembic revision: ${TARGET_ALEMBIC}"
else
  [[ -f "${DEPLOY_DIR}/last-good-alembic" ]] \
    || die "${DEPLOY_DIR}/last-good-alembic not found. Run a successful deploy first, or pass a target alembic rev as \$2."
  TARGET_ALEMBIC="$(cat "${DEPLOY_DIR}/last-good-alembic")"
  log "Using recorded last-good alembic revision: ${TARGET_ALEMBIC}"
fi

# ── 3. Determine current alembic revision ─────────────────────────────────────
log "Determining current alembic revision..."
ALEMBIC_CURRENT_OUTPUT="$(docker compose run --rm dhanradar-fastapi alembic current 2>/dev/null || echo "")"
CURRENT_ALEMBIC="$(echo "${ALEMBIC_CURRENT_OUTPUT}" | grep -oE '^[a-f0-9]+' | head -1 || echo "")"
if [[ -z "${CURRENT_ALEMBIC}" ]]; then
  CURRENT_ALEMBIC="base"
fi
log "Current alembic revision: ${CURRENT_ALEMBIC}"

# ── 4. DB downgrade (while current code still understands the schema) ──────────
DB_DOWNGRADED="no"

if [[ "${TARGET_ALEMBIC}" == "${CURRENT_ALEMBIC}" ]]; then
  log "Alembic revision unchanged (${CURRENT_ALEMBIC}) — no DB downgrade needed."
else
  warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  warn "DB DOWNGRADE requested: ${CURRENT_ALEMBIC} → ${TARGET_ALEMBIC}"
  warn "Alembic downgrade can be DESTRUCTIVE (irreversible data loss)."
  warn "Set CONFIRM_DB_DOWNGRADE=1 to proceed."
  warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  if [[ "${CONFIRM_DB_DOWNGRADE:-0}" == "1" ]]; then
    log "CONFIRM_DB_DOWNGRADE=1 set — proceeding with alembic downgrade to '${TARGET_ALEMBIC}'..."
    docker compose run --rm dhanradar-fastapi alembic downgrade "${TARGET_ALEMBIC}" \
      || die "Alembic downgrade failed. DB may be in an inconsistent state — inspect manually."
    log "Alembic downgrade to '${TARGET_ALEMBIC}' completed."
    DB_DOWNGRADED="yes (${CURRENT_ALEMBIC} → ${TARGET_ALEMBIC})"
  elif [[ "${ALLOW_SCHEMA_AHEAD:-0}" == "1" ]]; then
    # Code-only rollback: schema stays AHEAD of the rolled-back code. This is
    # safe ONLY for additive/backward-compatible migrations (old code ignores
    # new columns/tables). The operator must assert this explicitly.
    warn "ALLOW_SCHEMA_AHEAD=1 — code-only rollback; DB stays at ${CURRENT_ALEMBIC}."
    warn "Verified safe only if migrations ${TARGET_ALEMBIC}..${CURRENT_ALEMBIC} are additive."
    DB_DOWNGRADED="skipped (ALLOW_SCHEMA_AHEAD=1, schema left at ${CURRENT_ALEMBIC})"
  else
    die "DB is ahead of the rollback target (${CURRENT_ALEMBIC} > ${TARGET_ALEMBIC}). \
A code-only rollback would run old code against a newer schema. Choose one: \
set CONFIRM_DB_DOWNGRADE=1 to downgrade the schema too, or ALLOW_SCHEMA_AHEAD=1 \
to intentionally leave the schema ahead (additive migrations only). Refusing to \
guess — this protects the SEBI ai_recommendation_audit trail."
  fi
fi

# ── 5. Checkout target git SHA ────────────────────────────────────────────────
log "Checking out target SHA: ${TARGET_SHA}..."
git checkout "${TARGET_SHA}"
log "Checked out ${TARGET_SHA}."

# ── 6. Rebuild and restart ────────────────────────────────────────────────────
log "Rebuilding images at rollback SHA..."
docker compose build

log "Restarting all services..."
docker compose up -d

# ── 7. Health gate ────────────────────────────────────────────────────────────
HEALTH_TIMEOUT=180
POLL_INTERVAL=5
SERVICES=("dhanradar-fastapi" "dhanradar-nextjs")

log "Waiting for services to become healthy (timeout: ${HEALTH_TIMEOUT}s)..."
deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))

# Compose does not set container_name, so the real container is project-prefixed
# (e.g. dhanradar-dhanradar-fastapi-1). Resolve the container id via compose
# before inspecting — `docker inspect <service-name>` would not find it.
svc_health() {
  local cid
  cid="$(docker compose ps -q "$1" 2>/dev/null || echo "")"
  [[ -n "${cid}" ]] || { echo "missing"; return; }
  docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${cid}" 2>/dev/null || echo "missing"
}

all_healthy() {
  local svc
  for svc in "${SERVICES[@]}"; do
    [[ "$(svc_health "${svc}")" == "healthy" ]] || return 1
  done
  return 0
}

while ! all_healthy; do
  if (( $(date +%s) >= deadline )); then
    log "ERROR: Health gate timed out after ${HEALTH_TIMEOUT}s post-rollback."
    for svc in "${SERVICES[@]}"; do
      if [[ "$(svc_health "${svc}")" != "healthy" ]]; then
        log "--- Last 50 log lines for ${svc} ---"
        docker compose logs --tail=50 "${svc}" || true
      fi
    done
    exit 1
  fi
  sleep "${POLL_INTERVAL}"
done

# ── 8. Summary ────────────────────────────────────────────────────────────────
log "=== Rollback successful ==="
log "  Code SHA rolled back to : ${TARGET_SHA}"
log "  DB downgrade             : ${DB_DOWNGRADED}"
log "  Services: ${SERVICES[*]} — healthy"
