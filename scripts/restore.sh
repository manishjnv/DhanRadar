#!/usr/bin/env bash
# scripts/restore.sh — Restore DhanRadar Postgres + Redis from an R2 or local backup.
#
# !! DESTRUCTIVE !! This script overwrites the live Postgres database.
#                   Requires CONFIRM_RESTORE=1 to proceed.
#
# USAGE
#   CONFIRM_RESTORE=1 bash scripts/restore.sh <backup-prefix-or-local-path>
#
#   <backup-prefix-or-local-path> is either:
#     - An R2 UTC timestamp prefix, e.g. "20260607194500"
#       (the script downloads from s3://$R2_BACKUP_BUCKET/<prefix>/)
#     - An absolute or relative path to a local backup directory
#       (the script uses it directly without downloading)
#
# REQUIREMENTS
#   Same as backup.sh: repo root, .env, `aws` CLI, Docker Compose v2.
#
# SECRETS: this script loads .env but NEVER prints secret values.
#
set -euo pipefail

# ── Helpers ──────────────────────────────────────────────────────────────────

TIMESTAMP() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
log()  { echo "[$(TIMESTAMP)] $*"; }
die()  { echo "[$(TIMESTAMP)] ERROR: $*" >&2; exit 1; }
warn() { echo "[$(TIMESTAMP)] WARNING: $*" >&2; }

# ── 1. Preconditions ─────────────────────────────────────────────────────────

log "=== DhanRadar restore started ==="

# Safety gate: must opt in explicitly.
if [[ "${CONFIRM_RESTORE:-0}" != "1" ]]; then
  echo "" >&2
  echo "  !! RESTORE ABORTED !!" >&2
  echo "" >&2
  echo "  This operation OVERWRITES the live Postgres database." >&2
  echo "  To proceed, set the environment variable:" >&2
  echo "    CONFIRM_RESTORE=1" >&2
  echo "" >&2
  echo "  Example:" >&2
  echo "    CONFIRM_RESTORE=1 bash scripts/restore.sh <backup-prefix>" >&2
  echo "" >&2
  exit 1
fi

[[ $# -ge 1 ]] || die "Usage: bash scripts/restore.sh <backup-prefix-or-local-path>"
BACKUP_ARG="$1"

[[ -f "docker-compose.yml" ]] \
  || die "docker-compose.yml not found. Run from the repo root."

[[ -f ".env" ]] \
  || die ".env not found at repo root."

# Load ONLY the variables this script needs from .env. Do NOT `source` the
# whole file: docker-compose env_file tolerates values bash cannot (e.g. the
# multi-line JWT_PRIVATE_KEY PEM) and sourcing aborts the script (2026-06-11).
_env_get() { grep -E "^$1=" .env | head -1 | cut -d= -f2-; }
POSTGRES_PASSWORD="$(_env_get POSTGRES_PASSWORD)"
R2_ACCESS_KEY_ID="$(_env_get R2_ACCESS_KEY_ID)"
R2_SECRET_ACCESS_KEY="$(_env_get R2_SECRET_ACCESS_KEY)"
R2_BACKUP_BUCKET="$(_env_get R2_BACKUP_BUCKET)"
R2_ENDPOINT="$(_env_get R2_ENDPOINT)"
export POSTGRES_PASSWORD R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY \
       R2_BACKUP_BUCKET R2_ENDPOINT

_assert_var() {
  local name="$1"
  local val="${!name:-}"
  [[ -n "${val}" ]] || die "Required variable ${name} is not set or is empty in .env"
}
_assert_var POSTGRES_PASSWORD

command -v aws    > /dev/null 2>&1 || die "'aws' CLI not found on PATH."
command -v docker > /dev/null 2>&1 || die "'docker' not found on PATH."
docker compose version > /dev/null 2>&1 || die "'docker compose' (v2) not available."

# ── 2. Resolve backup source ─────────────────────────────────────────────────

RESTORE_DIR=""

# Heuristic: if the arg looks like a local path (starts with / or . or ~) use it directly.
if [[ "${BACKUP_ARG}" == /* || "${BACKUP_ARG}" == .* || "${BACKUP_ARG}" == ~* ]]; then
  RESTORE_DIR="${BACKUP_ARG}"
  [[ -d "${RESTORE_DIR}" ]] \
    || die "Local backup directory not found: ${RESTORE_DIR}"
  log "Using local backup dir: ${RESTORE_DIR}"
else
  # Treat as an R2 prefix — download to a temp dir.
  _assert_var R2_ACCESS_KEY_ID
  _assert_var R2_SECRET_ACCESS_KEY
  _assert_var R2_BACKUP_BUCKET
  _assert_var R2_ENDPOINT

  RESTORE_DIR="$(mktemp -d /tmp/dhanradar-restore-XXXXXX)"
  # A bare UTC stamp resolves under the backups/ prefix (see backup.sh §6).
  # An argument containing "/" is used verbatim (explicit prefix). The single
  # legacy root-level backup (20260611111632, pre-prefix) is restorable via
  # its local copy under /var/backups/dhanradar/ using the local-path form.
  BACKUP_ARG="${BACKUP_ARG%/}"
  if [[ "${BACKUP_ARG}" == */* ]]; then
    R2_SRC="s3://${R2_BACKUP_BUCKET}/${BACKUP_ARG}/"
  else
    R2_SRC="s3://${R2_BACKUP_BUCKET}/backups/${BACKUP_ARG}/"
  fi

  log "Downloading backup from R2: ${R2_SRC} → ${RESTORE_DIR} ..."
  # R2 creds via a private temp credentials file (chmod 600), not inline env
  # vars, so they never appear in the aws process's /proc/<pid>/environ.
  # The trap is registered BEFORE the secret is written so no failure window
  # can leave the file behind.
  R2_CRED_FILE="$(mktemp)"
  trap 'rm -f "${R2_CRED_FILE}"' EXIT
  chmod 600 "${R2_CRED_FILE}"
  printf '[default]\naws_access_key_id=%s\naws_secret_access_key=%s\n' \
    "${R2_ACCESS_KEY_ID}" "${R2_SECRET_ACCESS_KEY}" > "${R2_CRED_FILE}"

  # Fetch each expected artifact BY NAME — never `cp --recursive`: S3 object
  # keys may legally contain "/" or "..", and a recursive copy plants
  # key-derived paths relative to (or outside) RESTORE_DIR as root. Explicit
  # per-object destinations make key-based path traversal impossible
  # regardless of CLI behaviour. (Tier-B security review, 2026-06-12.)
  _r2_get() {
    AWS_SHARED_CREDENTIALS_FILE="${R2_CRED_FILE}" AWS_PROFILE=default \
      aws s3 cp "${R2_SRC}$1" "${RESTORE_DIR}/$1" \
        --endpoint-url "${R2_ENDPOINT}" \
        --no-progress
  }
  _r2_get "MANIFEST" || die "R2 download failed for MANIFEST. Check prefix and credentials."
  _r2_get "db.dump"  || die "R2 download failed for db.dump. Check prefix and credentials."
  _r2_get "redis-dump.rdb"          || warn "redis-dump.rdb not fetched (may be absent at source) — continuing."
  _r2_get "redis-appendonly.tar.gz" || warn "redis-appendonly.tar.gz not fetched (may be absent at source) — continuing."

  rm -f "${R2_CRED_FILE}"
  trap - EXIT
  log "Download complete."
fi

# ── 3. Verify MANIFEST checksums ─────────────────────────────────────────────

MANIFEST="${RESTORE_DIR}/MANIFEST"
[[ -f "${MANIFEST}" ]] || die "MANIFEST not found in backup dir: ${RESTORE_DIR}"

log "Verifying MANIFEST checksums ..."

# Read each file=... line and compare sha256.
checksum_ok=true
db_dump_verified=false
while IFS= read -r line; do
  if [[ "${line}" =~ ^file=([^[:space:]]+)[[:space:]]+size=[^[:space:]]+[[:space:]]+sha256=([^[:space:]]+) ]]; then
    fname="${BASH_REMATCH[1]}"
    expected_sha="${BASH_REMATCH[2]}"
    # Reject path traversal / unexpected names: a malicious MANIFEST from a
    # compromised R2 bucket could set fname=../../etc/shadow and have sha256sum
    # read an arbitrary host file. Positive allowlist of the only artifacts we write.
    case "${fname}" in
      db.dump|redis-dump.rdb|redis-appendonly.tar.gz) ;;
      *) die "MANIFEST lists an unexpected artifact name '${fname}' — refusing (possible tampering)." ;;
    esac
    fpath="${RESTORE_DIR}/${fname}"

    if [[ "${expected_sha}" == "absent" ]]; then
      # "absent" means the artifact was NOT produced at backup time. If a file
      # by that name nonetheless exists here, someone planted it — a crafted
      # MANIFEST must not be able to skip verification of a present file.
      if [[ -f "${fpath}" ]]; then
        die "MANIFEST marks ${fname} absent-at-backup-time but the file IS present — refusing (possible tampering)."
      fi
      warn "Artifact ${fname} was absent at backup time — skipping checksum."
      continue
    fi

    if [[ ! -f "${fpath}" ]]; then
      warn "Artifact ${fname} listed in MANIFEST but not found in restore dir — skipping."
      checksum_ok=false
      continue
    fi

    actual_sha="$(sha256sum "${fpath}" | awk '{print $1}')"
    if [[ "${actual_sha}" != "${expected_sha}" ]]; then
      die "Checksum MISMATCH for ${fname}: expected=${expected_sha} actual=${actual_sha}. Aborting restore — backup may be corrupt."
    fi
    log "  OK  ${fname} (sha256 verified)"
    if [[ "${fname}" == "db.dump" ]]; then
      db_dump_verified=true
    fi
  fi
done < "${MANIFEST}"

if [[ "${checksum_ok}" != "true" ]]; then
  die "One or more artifact checksum failures. Restore aborted."
fi
# A MANIFEST with zero file= lines (or with db.dump stripped) must never pass:
# verification is only meaningful if the artifact we restore was verified.
if [[ "${db_dump_verified}" != "true" ]]; then
  die "MANIFEST contained no verified db.dump entry — refusing (empty or stripped MANIFEST; possible tampering)."
fi
log "All checksums verified."

# ── 4. Read metadata from MANIFEST ───────────────────────────────────────────

BACKUP_STAMP="$(grep '^backup_utc=' "${MANIFEST}" | cut -d= -f2 || echo "unknown")"
BACKUP_GIT="$(grep '^git_sha=' "${MANIFEST}" | cut -d= -f2 || echo "unknown")"
BACKUP_ALEMBIC="$(grep '^alembic_rev=' "${MANIFEST}" | cut -d= -f2 || echo "unknown")"

log "Restoring backup: stamp=${BACKUP_STAMP} git=${BACKUP_GIT} alembic=${BACKUP_ALEMBIC}"

# ── 5. Postgres restore ───────────────────────────────────────────────────────
#
# PREFERRED APPROACH (full clean restore into a fresh DB — see runbook):
#   For a guaranteed clean state, drop and recreate the target database in a
#   psql session before running pg_restore. Steps documented in
#   docs/ops/backup-restore-runbook.md under "Full clean restore".
#
# This script uses --clean --if-exists which drops and recreates individual
# objects within the existing database — sufficient for most recoveries but
# may leave orphaned objects if the schema has changed significantly since
# the backup.
#
DB_DUMP="${RESTORE_DIR}/db.dump"
[[ -f "${DB_DUMP}" ]] || die "db.dump not found in restore dir."

log "Restoring Postgres from db.dump (--clean --if-exists) ..."

# TimescaleDB: the hypertable catalog must be put into restoring mode around
# pg_restore (timescaledb_pre_restore / timescaledb_post_restore), or restoring
# chunk catalogs fails. post_restore MUST run even when pg_restore fails —
# otherwise the database is left with timescaledb.restoring=on and is unusable.
docker compose exec -T dhanradar-postgres \
  psql -U dhanradar -d dhanradar -v ON_ERROR_STOP=1 \
  -c "CREATE EXTENSION IF NOT EXISTS timescaledb; SELECT timescaledb_pre_restore();" \
  > /dev/null \
  || die "timescaledb_pre_restore failed — aborting before pg_restore."

restore_rc=0
docker compose exec -T dhanradar-postgres \
  pg_restore \
    -U dhanradar \
    -d dhanradar \
    --clean \
    --if-exists \
    --exit-on-error \
  < "${DB_DUMP}" \
  || restore_rc=$?

docker compose exec -T dhanradar-postgres \
  psql -U dhanradar -d dhanradar -v ON_ERROR_STOP=1 \
  -c "SELECT timescaledb_post_restore();" \
  > /dev/null \
  || warn "timescaledb_post_restore FAILED — run it manually before serving traffic: SELECT timescaledb_post_restore();"

if (( restore_rc != 0 )); then
  die "pg_restore failed (exit ${restore_rc}). Check the error above. The database may be in a partially restored state."
fi

log "Postgres restore complete."

# ── 6. Redis restore (best-effort) ───────────────────────────────────────────
#
# Redis is a cache and task queue — all application state is in Postgres.
# Its data is regenerable (caches rebuild on demand; Celery tasks re-enqueue).
# Redis restore is therefore best-effort: we stop the service, replace the
# data files, and restart. Failure here is logged as a warning, not an abort.
#
REDIS_DATA_DIR="/data"
REDIS_RDB="${RESTORE_DIR}/redis-dump.rdb"
REDIS_AOF_TAR="${RESTORE_DIR}/redis-appendonly.tar.gz"

if [[ -f "${REDIS_RDB}" || -f "${REDIS_AOF_TAR}" ]]; then
  log "Stopping Redis for data file replacement ..."
  docker compose stop dhanradar-redis || warn "Could not stop Redis — attempting data copy anyway."

  if [[ -f "${REDIS_AOF_TAR}" ]]; then
    log "Extracting AOF/RDB tar into Redis container data dir ..."
    # Copy tar into container via stdin and extract in place.
    docker compose run --rm --no-deps \
      -v /dev/stdin:/dev/stdin \
      dhanradar-redis \
      sh -c "tar -xzf /dev/stdin -C ${REDIS_DATA_DIR}" \
      < "${REDIS_AOF_TAR}" \
      || warn "AOF tar extraction failed — Redis will start with existing or empty data."
  elif [[ -f "${REDIS_RDB}" ]]; then
    log "Copying dump.rdb into Redis container ..."
    docker compose run --rm --no-deps \
      dhanradar-redis \
      sh -c "cat > ${REDIS_DATA_DIR}/dump.rdb" \
      < "${REDIS_RDB}" \
      || warn "dump.rdb copy failed — Redis will start with existing or empty data."
  fi

  log "Restarting Redis ..."
  docker compose start dhanradar-redis \
    || warn "Redis failed to start after restore. Investigate manually."
else
  log "No Redis artifacts found — skipping Redis restore (caches will rebuild)."
fi

# ── 7. Post-restore summary ───────────────────────────────────────────────────

echo ""
log "=== Restore complete ==="
log "  Backup stamp : ${BACKUP_STAMP}"
log "  Backup git   : ${BACKUP_GIT}"
log "  Backup alembic: ${BACKUP_ALEMBIC}"
echo ""
log "NEXT STEPS — verify the restore before returning the service to production:"
log "  1. Check current alembic revision matches the code:"
log "       docker compose run --rm dhanradar-fastapi alembic current"
log "  2. Spot-check row counts:"
log "       docker compose exec -T dhanradar-postgres psql -U dhanradar -d dhanradar -c 'SELECT COUNT(*) FROM auth.users;'"
log "       docker compose exec -T dhanradar-postgres psql -U dhanradar -d dhanradar -c 'SELECT COUNT(*) FROM ai_recommendation_audit;'"
log "  3. If the backup alembic rev does not match the current code head, run:"
log "       docker compose run --rm dhanradar-fastapi alembic upgrade head"
log "  4. Restart any dependent services if Redis was restored."
log "  See docs/ops/backup-restore-runbook.md for full verification steps."
