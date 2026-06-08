#!/usr/bin/env bash
# =============================================================================
# DhanRadar — KVM4 deploy script
# Run from the repo root on the KVM4 box.
#
# NEVER-TOUCH (enforced below — never override):
#   - Host /etc/cloudflared/config.yml and the host cloudflared systemd service.
#     That is the SSH lifeline tunnel for the box. DhanRadar uses its own
#     dhanradar-cloudflared CONTAINER; never touch the host service.
#   - Containers/volumes whose names start with etip_, roadmap, trendsmap.
#   - pkill / killall — can self-kill the SSH shell (known incident).
#   - Bare docker stop / docker rm / docker system prune.
#
# Every Docker operation in this script is scoped to:
#   docker compose -p dhanradar -f docker-compose.yml ...
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
COMPOSE="docker compose -p dhanradar -f docker-compose.yml"

# Health-poll settings
POLL_INTERVAL=5          # seconds between health checks
DB_TIMEOUT=120           # max seconds to wait for postgres + redis
APP_TIMEOUT=120          # max seconds to wait for fastapi + nextjs

# Colours (safe — only used in terminal messages, not in logic)
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RESET='\033[0m'

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

info()  { echo -e "${GREEN}[deploy]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[warn]${RESET}  $*" >&2; }
abort() { echo -e "${RED}[abort]${RESET} $*" >&2; exit 1; }

# wait_healthy <service-name> <timeout-secs>
# Polls the Docker health status of the given compose service until it is
# "healthy" or the timeout is exceeded.  Aborts on timeout.
wait_healthy() {
    local service="$1"
    local timeout="$2"
    local elapsed=0
    local seen=0   # have we ever resolved a container id for this service?

    info "Waiting for ${service} to become healthy (timeout ${timeout}s)…"

    while true; do
        # Resolve the container id for this compose service
        # `|| true`: under `set -o pipefail`, `… | head -1` can exit 141 (SIGPIPE)
        # and abort the whole deploy mid-wait. Never let the probe kill the run.
        local cid
        cid=$($COMPOSE ps -q "${service}" 2>/dev/null | head -1 || true)

        if [[ -n "${cid}" ]]; then
            seen=1
            local status
            status=$(docker inspect --format '{{.State.Health.Status}}' "${cid}" 2>/dev/null || echo "unknown")
            if [[ "${status}" == "healthy" ]]; then
                info "${service} is healthy."
                return 0
            fi
        fi

        if (( elapsed >= timeout )); then
            if (( seen == 0 )); then
                # Container never came up at all — surface the likely cause instead
                # of just "unhealthy" (build/up failed, or the Docker daemon is down).
                abort "${service} container never started within ${timeout}s (build/up failed or Docker daemon down?). Check: $COMPOSE ps; $COMPOSE logs ${service}"
            fi
            abort "${service} did not become healthy within ${timeout}s. Check logs: $COMPOSE logs ${service}"
        fi

        sleep "${POLL_INTERVAL}"
        elapsed=$(( elapsed + POLL_INTERVAL ))
    done
}

# -----------------------------------------------------------------------------
# Preflight checks (run before deploy and rollback)
# -----------------------------------------------------------------------------
preflight() {
    # Must run from the repo root (docker-compose.yml present)
    if [[ ! -f "docker-compose.yml" ]]; then
        abort "docker-compose.yml not found. Run this script from the repo root."
    fi

    # .env must exist
    if [[ ! -f ".env" ]]; then
        abort ".env not found at repo root. Create it from .env.example and fill all secrets (see docs/infra-notes.md)."
    fi

    # docker compose must be available
    if ! docker compose version &>/dev/null; then
        abort "'docker compose' is not available. Install Docker Engine with the Compose plugin."
    fi

    # Warn if not on main
    local branch
    branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
    if [[ "${branch}" != "main" ]]; then
        warn "Current branch is '${branch}', not 'main'. The GitHub production environment is main-gated. Proceed with caution."
    fi

    # Print summary
    local sha
    sha=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    info "Preflight OK — branch: ${branch}  sha: ${sha}"
}

# -----------------------------------------------------------------------------
# status subcommand
# -----------------------------------------------------------------------------
cmd_status() {
    info "Service status:"
    $COMPOSE ps

    echo ""
    info "Per-service health:"
    local services=(
        dhanradar-postgres
        dhanradar-redis
        dhanradar-fastapi
        dhanradar-nextjs
        dhanradar-celery-batch
        dhanradar-celery-mood
        dhanradar-celery-misc
        dhanradar-celery-beat
        dhanradar-cloudflared
    )
    for svc in "${services[@]}"; do
        local cid
        cid=$($COMPOSE ps -q "${svc}" 2>/dev/null | head -1 || true)
        if [[ -z "${cid}" ]]; then
            echo "  ${svc}: not running"
        else
            local hstatus
            hstatus=$(docker inspect --format '{{.State.Health.Status}}' "${cid}" 2>/dev/null || echo "no-healthcheck")
            local rstatus
            rstatus=$(docker inspect --format '{{.State.Status}}' "${cid}" 2>/dev/null || echo "unknown")
            echo "  ${svc}: state=${rstatus}  health=${hstatus}"
        fi
    done
}

# -----------------------------------------------------------------------------
# deploy subcommand
# -----------------------------------------------------------------------------
cmd_deploy() {
    preflight

    # 1. Build images
    info "Building images…"
    $COMPOSE build

    # 2. Bring up the data tier
    info "Starting data tier (postgres + redis)…"
    $COMPOSE up -d dhanradar-postgres dhanradar-redis

    # 3. Wait for data tier to be healthy
    wait_healthy dhanradar-postgres "${DB_TIMEOUT}"
    wait_healthy dhanradar-redis    "${DB_TIMEOUT}"

    # 4. Run migrations on the NEW image before serving traffic.
    #    Pre-serve ordering: the new code must never run against the old schema.
    #    DhanRadar migrations are additive, so the old code is safe on the new schema.
    info "Running Alembic migrations (alembic upgrade head)…"
    # -T: no pseudo-TTY — required when run non-interactively over SSH (else
    # `compose run` errors "the input device is not a TTY").
    # `python -m alembic` (NOT bare `alembic`): the package is copied to /app but
    # not pip-installed, so only an invocation that puts CWD on sys.path can import
    # `dhanradar` from alembic/env.py. uvicorn does this implicitly; bare `alembic`
    # does not (ModuleNotFoundError). `python -m` adds CWD, matching the CI job.
    $COMPOSE run --rm -T dhanradar-fastapi python -m alembic upgrade head

    # 5. Bring up the full stack
    info "Starting full stack…"
    $COMPOSE up -d

    # 6. Wait for app services to be healthy
    wait_healthy dhanradar-fastapi "${APP_TIMEOUT}"
    wait_healthy dhanradar-nextjs  "${APP_TIMEOUT}"

    # 7. Smoke test — curl the health endpoint from inside the fastapi container
    info "Running smoke test against /api/v1/health…"
    local smoke_exit=0
    $COMPOSE exec -T dhanradar-fastapi \
        python -c \
        "import urllib.request,sys; r=urllib.request.urlopen('http://localhost:8000/api/v1/health'); sys.exit(0 if r.status==200 else 1)" \
        || smoke_exit=$?

    if (( smoke_exit != 0 )); then
        abort "Smoke test FAILED — /api/v1/health did not return 200. Check logs: $COMPOSE logs dhanradar-fastapi"
    fi

    info "Smoke test passed — API returned 200."
    info "Deploy complete."
    echo ""
    cmd_status
}

# -----------------------------------------------------------------------------
# rollback subcommand
# -----------------------------------------------------------------------------
cmd_rollback() {
    local ref="${1:-}"

    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${RED}║  ROLLBACK WARNING                                                ║${RESET}"
    echo -e "${RED}║                                                                  ║${RESET}"
    echo -e "${RED}║  This subcommand redeploys the app at the specified git ref.     ║${RESET}"
    echo -e "${RED}║  It does NOT run alembic downgrade — schema is left as-is.      ║${RESET}"
    echo -e "${RED}║  For schema downgrade (DANGEROUS, can destroy data), follow the  ║${RESET}"
    echo -e "${RED}║  MANUAL procedure in docs/ops/deploy-runbook.md §6b.            ║${RESET}"
    echo -e "${RED}║  B37 (DB backup) must exist and be verified before any downgrade.║${RESET}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════════╝${RESET}"
    echo ""

    if [[ -z "${ref}" ]]; then
        abort "Usage: $0 rollback <git-ref>  (e.g. a commit SHA or tag)"
    fi

    preflight

    local current_sha
    current_sha=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    info "Current HEAD: ${current_sha}"
    info "Rollback target ref: ${ref}"

    # Resolve the ref to a short SHA so the operator can confirm
    local target_sha
    target_sha=$(git rev-parse --short "${ref}" 2>/dev/null) \
        || abort "Cannot resolve git ref '${ref}'. Fetch first if needed: git fetch origin"

    info "Resolved target SHA: ${target_sha}"

    local current_full
    current_full=$(git rev-parse HEAD 2>/dev/null || echo "")
    local target_full
    target_full=$(git rev-parse "${ref}" 2>/dev/null || echo "")

    if [[ "${current_full}" == "${target_full}" ]]; then
        info "Working tree is already at ${target_sha}. Running deploy…"
    else
        warn "Working tree is at ${current_sha}, not at the rollback target ${target_sha}."
        warn "Please check out the target ref manually, then re-run:"
        warn "  git checkout ${ref}"
        warn "  bash scripts/deploy.sh deploy"
        abort "Rollback aborted — check out the desired ref first, then run 'deploy'."
    fi

    # If already at the desired ref, just redeploy
    cmd_deploy
}

# -----------------------------------------------------------------------------
# help subcommand
# -----------------------------------------------------------------------------
cmd_help() {
    cat <<'EOF'
DhanRadar deploy script — run from the repo root on the KVM4 box.

Usage:
  bash scripts/deploy.sh [subcommand]

Subcommands:
  deploy              Build images, migrate, bring up all 9 services (default).
  status              Show per-service state and health.
  rollback <ref>      Redeploy at <ref> (app-only; does NOT touch schema).
                      Check out the desired ref first, then this command re-deploys.
                      For schema downgrade see docs/ops/deploy-runbook.md §6b.
  help                Show this message.

Safety rules enforced by this script:
  - Every Docker op is scoped to: docker compose -p dhanradar -f docker-compose.yml
  - Never bare docker stop/rm/prune.
  - Never pkill/killall.
  - Never touches host cloudflared service/config (SSH lifeline — not ours).
  - Migrations run pre-serve on the new image, before app traffic.
  - Smoke test gates the deploy; non-200 aborts with a non-zero exit.

See docs/ops/deploy-runbook.md for the full runbook.
EOF
}

# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
SUBCOMMAND="${1:-deploy}"

case "${SUBCOMMAND}" in
    deploy)
        cmd_deploy
        ;;
    status)
        cmd_status
        ;;
    rollback)
        cmd_rollback "${2:-}"
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        abort "Unknown subcommand '${SUBCOMMAND}'. Run '$0 help' for usage."
        ;;
esac
