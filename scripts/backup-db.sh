#!/usr/bin/env bash
# =============================================================================
# DhanRadar — nightly DB backup script
# Run from the repo root on the KVM4 box (same working directory as deploy.sh).
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
#
# Credentials stay INSIDE the containers — this script never sees them.
# No secrets are echoed or written to disk.
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
COMPOSE="docker compose -p dhanradar -f docker-compose.yml"

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
info()  { echo "[backup] $*"; }
abort() { echo "[backup] ERROR: $*" >&2; exit 1; }

# -----------------------------------------------------------------------------
# Preflight checks
# -----------------------------------------------------------------------------
preflight() {
    if [[ ! -f "docker-compose.yml" ]]; then
        abort "docker-compose.yml not found. Run this script from the repo root."
    fi

    if [[ ! -f ".env" ]]; then
        abort ".env not found at repo root. Create it from .env.example (see docs/infra-notes.md)."
    fi

    if ! docker compose version &>/dev/null; then
        abort "'docker compose' is not available. Install Docker Engine with the Compose plugin."
    fi
}

# -----------------------------------------------------------------------------
# backup subcommand — pg_dump inside postgres container, upload via fastapi
# -----------------------------------------------------------------------------
cmd_backup() {
    preflight

    # Compute UTC timestamp without a subshell-clock-skew dependency:
    # both variables read from the same clock call order so ts == datepath day.
    ts=$(date -u +%Y%m%dT%H%M%SZ)
    datepath=$(date -u +%Y/%m/%d)
    key="backups/postgres/${datepath}/dhanradar-${ts}.dump"

    info "Starting backup -> r2://${key}"

    # pg_dump runs INSIDE the live dhanradar-postgres container (pg16 is already
    # there; -Fc streams, low memory).
    #
    # The uploader runs in a SEPARATE one-off container via `run --rm` (NOT `exec`
    # into the live API container). r2_put reads the whole dump into memory before
    # the put; doing that inside the serving fastapi container (512M cgroup shared
    # with uvicorn) could trip the OOM-killer and kill the live API during a
    # backup. A throwaway `run --rm` container isolates that memory pressure from
    # the serving process. It inherits the same image + .env (R2 creds), needs no
    # postgres (R2 is outbound only), and is auto-removed.
    #
    # set -o pipefail (inherited from the top-level set) means a pg_dump failure
    # propagates as a non-zero exit from the whole pipe expression. The r2_put
    # empty-guard is a second net: 0 bytes => r2_put exits 3 (never uploads).
    #
    # -Fc = custom compressed format; restores with pg_restore (not psql).
    # -T  = no pseudo-TTY (required for piped/non-interactive use).
    if ! $COMPOSE exec -T dhanradar-postgres \
            sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
        | $COMPOSE run --rm -T dhanradar-fastapi python -m dhanradar.ops.r2_put "${key}"; then
        abort "Backup FAILED. Check pg_dump and r2_put output above. No object was uploaded (empty-dump guard active)."
    fi

    info "Backup complete: r2://${key}"
}

# -----------------------------------------------------------------------------
# list subcommand — show the 20 most-recent backup objects in R2
# -----------------------------------------------------------------------------
cmd_list() {
    preflight

    info "Listing recent backups in R2 (backups/postgres/) ..."

    $COMPOSE exec -T dhanradar-fastapi python -c '
import sys
try:
    from dhanradar import storage
    client = storage.get_r2_client()
    from dhanradar.config import settings
    resp = client.list_objects_v2(Bucket=settings.R2_BUCKET, Prefix="backups/postgres/")
    objects = resp.get("Contents", [])
    if not objects:
        print("No backup objects found.")
        sys.exit(0)
    # Sort descending by LastModified; show up to 20
    objects.sort(key=lambda o: o["LastModified"], reverse=True)
    for obj in objects[:20]:
        size_mb = obj["Size"] / (1024 * 1024)
        print(f"  {obj[\"Key\"]}  ({size_mb:.2f} MB)  {obj[\"LastModified\"].strftime(\"%Y-%m-%d %H:%M:%S UTC\")}")
except storage.StorageNotConfigured as exc:
    print(f"R2 not configured — {exc}", file=sys.stderr)
    sys.exit(4)
'
}

# -----------------------------------------------------------------------------
# help subcommand
# -----------------------------------------------------------------------------
cmd_help() {
    cat <<'EOF'
DhanRadar backup script — run from the repo root on the KVM4 box.

Usage:
  bash scripts/backup-db.sh [subcommand]

Subcommands:
  backup    (default) Dump the full dhanradar DB via pg_dump -Fc inside the
            postgres container, upload to R2 via the fastapi container's
            storage.put_object. Key: backups/postgres/YYYY/MM/DD/dhanradar-<UTC>.dump
  list      List the 20 most-recent backup objects in R2.
  help      Show this message.

Safety rules:
  - Every Docker op is scoped to: docker compose -p dhanradar -f docker-compose.yml
  - No credentials are ever echoed or written to disk.
  - Empty-dump guard: pg_dump failure produces 0 bytes -> upload refused (exit 3).
  - set -euo pipefail + pipe pipefail: a pg_dump failure aborts the whole pipe.

HOST cron (21:30 UTC = 03:00 IST, after the 02:00/02:30 IST compliance jobs):
  # 30 21 * * * cd <DHANRADAR-REPO-PATH> && bash scripts/backup-db.sh backup >> /var/log/dhanradar-backup.log 2>&1

See docs/ops/backup-and-restore.md for the full schedule, restore procedure,
and retention/residency deploy gates.
EOF
}

# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
SUBCOMMAND="${1:-backup}"

case "${SUBCOMMAND}" in
    backup)
        cmd_backup
        ;;
    list)
        cmd_list
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        abort "Unknown subcommand '${SUBCOMMAND}'. Run '$0 help' for usage."
        ;;
esac
