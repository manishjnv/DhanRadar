#!/usr/bin/env bash
# scripts/deploy.sh — Idempotent deploy script for DhanRadar on KVM4.
# Runs on the Linux host; must be executed from the repo root.
# Usage: bash scripts/deploy.sh
#   DEPLOY_SKIP_PULL=1  — skip git pull (useful when HEAD is already at target SHA)
set -euo pipefail

DEPLOY_DIR=".deploy"
TIMESTAMP() { date '+%Y-%m-%dT%H:%M:%S'; }
log() { echo "[$(TIMESTAMP)] $*"; }
die() { echo "[$(TIMESTAMP)] ERROR: $*" >&2; exit 1; }

# ── 1. Preconditions ──────────────────────────────────────────────────────────
log "=== DhanRadar deploy started ==="

[[ -f "docker-compose.yml" ]] \
  || die "docker-compose.yml not found. Run from the repo root."

[[ -f ".env" ]] \
  || die ".env not found at repo root. Secrets file is required."

docker compose version > /dev/null 2>&1 \
  || die "docker compose (v2) is not available. Install Docker Compose v2."

mkdir -p "${DEPLOY_DIR}"

# ── 2. Record current good state ──────────────────────────────────────────────
log "Recording current state for rollback..."

CURRENT_SHA="$(git rev-parse HEAD)"
GIT_STATUS="$(git status --porcelain)"
if [[ -n "${GIT_STATUS}" ]]; then
  log "WARNING: Working tree is dirty — recording SHA anyway but deploy may not be reproducible."
fi
echo "${CURRENT_SHA}" > "${DEPLOY_DIR}/last-good-sha"
log "Current git SHA: ${CURRENT_SHA}"

log "Capturing current alembic revision (pre-migration)..."
ALEMBIC_CURRENT_OUTPUT="$(docker compose run --rm dhanradar-fastapi alembic current 2>/dev/null || echo "")"
# Parse the revision id from output like "abc1234 (head)" or "base"
ALEMBIC_REV="$(echo "${ALEMBIC_CURRENT_OUTPUT}" | grep -oE '^[a-f0-9]+' | head -1 || echo "")"
if [[ -z "${ALEMBIC_REV}" ]]; then
  log "Could not determine alembic revision (stack may not be up or DB fresh) — defaulting to 'base'."
  ALEMBIC_REV="base"
fi
echo "${ALEMBIC_REV}" > "${DEPLOY_DIR}/last-good-alembic"
log "Current alembic revision: ${ALEMBIC_REV}"

# ── 3. git pull ───────────────────────────────────────────────────────────────
if [[ "${DEPLOY_SKIP_PULL:-0}" == "1" ]]; then
  log "DEPLOY_SKIP_PULL=1 set — skipping git pull."
else
  BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || echo "")"
  if [[ -z "${BRANCH}" ]]; then
    log "NOTICE: HEAD is in detached state — skipping git pull."
  else
    log "Pulling latest commits on branch '${BRANCH}'..."
    git pull --ff-only
  fi
fi

# ── 4. Build images ───────────────────────────────────────────────────────────
log "Building Docker images..."
docker compose build

# ── 5. Run migrations ─────────────────────────────────────────────────────────
log "Running Alembic migrations: alembic upgrade head..."
docker compose run --rm dhanradar-fastapi alembic upgrade head \
  || die "Alembic upgrade failed. Aborting deploy. DB is still at pre-deploy revision. Re-run rollback if needed."
log "Migrations applied successfully."

# ── 6. Bring stack up ────────────────────────────────────────────────────────
log "Starting all services (docker compose up -d)..."
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
    log "ERROR: Health gate timed out after ${HEALTH_TIMEOUT}s."
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

# ── 8. Success ────────────────────────────────────────────────────────────────
NEW_SHA="$(git rev-parse HEAD)"
echo "${NEW_SHA}" > "${DEPLOY_DIR}/last-good-sha"

log "=== Deploy successful ==="
log "  Git SHA : ${NEW_SHA}"
log "  Alembic : head (0009)"
log "  Services: ${SERVICES[*]} — healthy"
log "  Public reachability is via the cloudflared tunnel — no host ports exposed."
