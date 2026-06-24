#!/usr/bin/env bash
# scripts/backup.sh — Nightly backup of DhanRadar Postgres + Redis to Cloudflare R2
# (target: India-resident bucket; residency NOT yet verified — see B34 in BLOCKERS.md).
#
# REQUIREMENTS
#   - Run from the repo root (docker-compose.yml must exist in CWD).
#   - .env must exist and export POSTGRES_PASSWORD, R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
#     R2_SECRET_ACCESS_KEY, R2_BACKUP_BUCKET, R2_ENDPOINT.
#   - `aws` CLI must be installed and on PATH (used with --endpoint-url for R2 / S3-compat).
#   - Docker Compose v2 must be available as `docker compose`.
#
# USAGE
#   bash scripts/backup.sh
#
# CONFIGURABLE ENV VARS (override before calling; defaults shown)
#   BACKUP_DIR=/var/backups/dhanradar
#   LOCAL_RETENTION_DAYS=7          # delete local backup dirs older than N days
#   MAX_LOCAL_PCT=10               # hard cap: local backups <= N% of total disk
#   AGE_RECIPIENT_FILE=/etc/dhanradar-keys/backup_age.pub  # age public recipient
#
# ENCRYPTION: artifacts are age-encrypted (recipient above) BEFORE upload. The
#   matching identity /etc/dhanradar-keys/backup_age.key (0600) decrypts them —
#   KEEP AN OFFLINE COPY of it, or backups are unrecoverable if the box is lost.
#   Restore with: bash scripts/restore-db.sh [STAMP|latest] [TARGET_DB]
#
# SECRETS: this script loads .env but NEVER prints secret values.
#
set -euo pipefail

# ── Helpers ──────────────────────────────────────────────────────────────────

TIMESTAMP() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
log()  { echo "[$(TIMESTAMP)] $*"; }
die()  { echo "[$(TIMESTAMP)] ERROR: $*" >&2; exit 1; }

# ── 1. Preconditions ─────────────────────────────────────────────────────────

log "=== DhanRadar backup started ==="

[[ -f "docker-compose.yml" ]] \
  || die "docker-compose.yml not found. Run from the repo root."

[[ -f ".env" ]] \
  || die ".env not found at repo root."

# Load ONLY the variables this script needs from .env. Do NOT `source` the
# whole file: docker-compose env_file tolerates values bash cannot (e.g. the
# multi-line JWT_PRIVATE_KEY PEM), and sourcing it aborts the backup
# ("PRIVATE: command not found" — found on the first live run, 2026-06-11).
_env_get() { grep -E "^$1=" .env | head -1 | cut -d= -f2-; }
POSTGRES_PASSWORD="$(_env_get POSTGRES_PASSWORD)"
R2_ACCOUNT_ID="$(_env_get R2_ACCOUNT_ID)"
R2_ACCESS_KEY_ID="$(_env_get R2_ACCESS_KEY_ID)"
R2_SECRET_ACCESS_KEY="$(_env_get R2_SECRET_ACCESS_KEY)"
R2_BACKUP_BUCKET="$(_env_get R2_BACKUP_BUCKET)"
R2_ENDPOINT="$(_env_get R2_ENDPOINT)"
export POSTGRES_PASSWORD R2_ACCOUNT_ID R2_ACCESS_KEY_ID \
       R2_SECRET_ACCESS_KEY R2_BACKUP_BUCKET R2_ENDPOINT

# Assert required R2 variables are present and non-empty (no values printed).
_assert_var() {
  local name="$1"
  local val="${!name:-}"
  [[ -n "${val}" ]] || die "Required variable ${name} is not set or is empty in .env"
}
_assert_var R2_ACCOUNT_ID
_assert_var R2_ACCESS_KEY_ID
_assert_var R2_SECRET_ACCESS_KEY
_assert_var R2_BACKUP_BUCKET
_assert_var R2_ENDPOINT
_assert_var POSTGRES_PASSWORD

command -v aws  > /dev/null 2>&1 || die "'aws' CLI not found on PATH. Install the AWS CLI v2."
command -v docker > /dev/null 2>&1 || die "'docker' not found on PATH."
docker compose version > /dev/null 2>&1 || die "'docker compose' (v2) not available."

# ── 2. Create timestamped work directory ────────────────────────────────────

BACKUP_DIR="${BACKUP_DIR:-/var/backups/dhanradar}"
UTC_STAMP="$(date -u '+%Y%m%d%H%M%S')"
WORK_DIR="${BACKUP_DIR}/${UTC_STAMP}"

mkdir -p "${WORK_DIR}"
log "Work directory: ${WORK_DIR}"

# ── 3. Postgres logical backup ───────────────────────────────────────────────

DB_DUMP="${WORK_DIR}/db.dump"
log "Running pg_dump (custom format, compressed) ..."

docker compose exec -T dhanradar-postgres \
  pg_dump -U dhanradar -d dhanradar -Fc \
  > "${DB_DUMP}"

DB_SIZE="$(stat -c '%s' "${DB_DUMP}" 2>/dev/null || stat -f '%z' "${DB_DUMP}")"
# Sanity check: a non-empty pg_dump of any real DB should exceed 10 KB.
MIN_DUMP_BYTES=10240
if (( DB_SIZE < MIN_DUMP_BYTES )); then
  die "pg_dump produced only ${DB_SIZE} bytes — suspiciously small. Aborting to avoid uploading a corrupt dump."
fi
log "pg_dump: ${DB_SIZE} bytes written to db.dump"

# ── 4. Redis backup ──────────────────────────────────────────────────────────

log "Triggering Redis BGSAVE ..."
docker compose exec -T dhanradar-redis redis-cli BGSAVE > /dev/null

# Poll INFO persistence until rdb_bgsave_in_progress:0 (timeout 60s).
BGSAVE_TIMEOUT=60
BGSAVE_DEADLINE=$(( $(date +%s) + BGSAVE_TIMEOUT ))
while true; do
  IN_PROGRESS="$(docker compose exec -T dhanradar-redis \
    redis-cli INFO persistence \
    | grep 'rdb_bgsave_in_progress' \
    | tr -d '[:space:]' \
    | cut -d: -f2)"
  if [[ "${IN_PROGRESS}" == "0" ]]; then
    log "Redis BGSAVE complete."
    break
  fi
  if (( $(date +%s) >= BGSAVE_DEADLINE )); then
    die "Redis BGSAVE did not complete within ${BGSAVE_TIMEOUT}s."
  fi
  sleep 2
done

# Copy dump.rdb out of the container.
# Redis 7-alpine default data dir is /data.
REDIS_DATA_DIR="/data"
REDIS_RDB="${WORK_DIR}/redis-dump.rdb"
docker compose exec -T dhanradar-redis cat "${REDIS_DATA_DIR}/dump.rdb" \
  > "${REDIS_RDB}" \
  || log "WARNING: dump.rdb not found in container — Redis may not have written an RDB yet (AOF-only). Continuing."

# Copy the AOF directory (appendonly.aof or appendonlydir/ depending on Redis version).
# Redis 7 uses a multi-file AOF under appendonlydir/; fall back gracefully.
REDIS_AOF_TAR="${WORK_DIR}/redis-appendonly.tar.gz"
docker compose exec -T dhanradar-redis \
  tar -czf - -C "${REDIS_DATA_DIR}" . \
  > "${REDIS_AOF_TAR}" \
  || log "WARNING: Could not tar Redis data dir — AOF may be empty. Continuing."

log "Redis artifacts written to ${WORK_DIR}"

# ── 4b. Encrypt artifacts (age) BEFORE they leave the box ────────────────────
# Backups contain investor data. Encrypt at rest with age so a leaked R2 key (or
# a stolen backup file) is useless without the offline identity key
# (/etc/dhanradar-keys/backup_age.key — KEEP AN OFFLINE COPY or backups are
# unrecoverable if the box is lost). Restore decrypts via scripts/restore-db.sh.
# Fail-closed: refuse to upload unencrypted if age / the recipient is missing.
AGE_RECIPIENT_FILE="${AGE_RECIPIENT_FILE:-/etc/dhanradar-keys/backup_age.pub}"
command -v age > /dev/null 2>&1 \
  || die "'age' not installed but backup encryption is required (apt-get install age)."
[[ -s "${AGE_RECIPIENT_FILE}" ]] \
  || die "age recipient ${AGE_RECIPIENT_FILE} missing/empty — refusing to write unencrypted backups."
AGE_RECIPIENT="$(grep -m1 '^age1' "${AGE_RECIPIENT_FILE}" | tr -d '[:space:]')"
[[ -n "${AGE_RECIPIENT}" ]] || die "no age1... recipient found in ${AGE_RECIPIENT_FILE}."
log "Encrypting artifacts with age (recipient ${AGE_RECIPIENT:0:14}...) ..."
for _f in "${DB_DUMP}" "${REDIS_RDB}" "${REDIS_AOF_TAR}"; do
  [[ -s "${_f}" ]] || continue
  age -r "${AGE_RECIPIENT}" -o "${_f}.age" "${_f}" || die "age encryption failed for ${_f}"
  rm -f "${_f}"
done
# Point the manifest/upload at the encrypted artifacts.
DB_DUMP="${DB_DUMP}.age"
REDIS_RDB="${REDIS_RDB}.age"
REDIS_AOF_TAR="${REDIS_AOF_TAR}.age"
DB_SIZE="$(stat -c '%s' "${DB_DUMP}" 2>/dev/null || echo 0)"
log "Artifacts encrypted (age)."

# ── 5. Write MANIFEST ────────────────────────────────────────────────────────

MANIFEST="${WORK_DIR}/MANIFEST"
GIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo "unknown")"

# Best-effort: alembic current (needs dhanradar-fastapi service image).
# MUST be `python -m alembic`, not bare `alembic`: the console script does not
# put CWD (/app) on sys.path, so env.py's `from dhanradar...` import fails
# (found 2026-06-12 — every prior MANIFEST recorded alembic_rev=unavailable).
ALEMBIC_REV="$(docker compose run --rm --quiet dhanradar-fastapi \
  python -m alembic current 2>/dev/null \
  | grep -oE '^[a-f0-9]+' | head -1 \
  || echo "unavailable")"
[[ -n "${ALEMBIC_REV}" ]] || ALEMBIC_REV="unavailable"

sha256_of() {
  local f="$1"
  if [[ -s "${f}" ]]; then
    sha256sum "${f}" | awk '{print $1}'
  else
    echo "absent"
  fi
}

{
  echo "backup_utc=${UTC_STAMP}"
  echo "git_sha=${GIT_SHA}"
  echo "alembic_rev=${ALEMBIC_REV}"
  echo "encryption=age recipient=${AGE_RECIPIENT}"
  echo ""
  echo "file=db.dump.age size=${DB_SIZE} sha256=$(sha256_of "${DB_DUMP}")"
  echo "file=redis-dump.rdb.age size=$(stat -c '%s' "${REDIS_RDB}" 2>/dev/null || echo 0) sha256=$(sha256_of "${REDIS_RDB}")"
  echo "file=redis-appendonly.tar.gz.age size=$(stat -c '%s' "${REDIS_AOF_TAR}" 2>/dev/null || echo 0) sha256=$(sha256_of "${REDIS_AOF_TAR}")"
} > "${MANIFEST}"

log "MANIFEST written."

# ── 6. Upload to R2 ──────────────────────────────────────────────────────────

# Backups live under the backups/ prefix: the bucket is shared with app assets,
# and the R2 lifecycle rule (7-yr retention, B37) is scoped to this prefix so it
# can never expire asset objects. Root-level stamps (pre-2026-06-12) are legacy.
R2_PREFIX="backups/${UTC_STAMP}"
R2_DEST="s3://${R2_BACKUP_BUCKET}/${R2_PREFIX}/"

log "Uploading backup to R2: ${R2_DEST} ..."

# R2 creds go in a private temp credentials file (chmod 600) rather than inline
# env vars, so they never appear in the aws process's /proc/<pid>/environ
# (readable by same-UID/root processes on the shared KVM4 box). The trap is
# registered BEFORE the secret is written so no failure window leaks the file.
R2_CRED_FILE="$(mktemp)"
trap 'rm -f "${R2_CRED_FILE}"' EXIT
chmod 600 "${R2_CRED_FILE}"
printf '[default]\naws_access_key_id=%s\naws_secret_access_key=%s\n' \
  "${R2_ACCESS_KEY_ID}" "${R2_SECRET_ACCESS_KEY}" > "${R2_CRED_FILE}"

AWS_SHARED_CREDENTIALS_FILE="${R2_CRED_FILE}" AWS_PROFILE=default \
  aws s3 cp \
    --recursive \
    "${WORK_DIR}/" \
    "${R2_DEST}" \
    --endpoint-url "${R2_ENDPOINT}" \
    --no-progress \
  || die "R2 upload failed. A backup that is not offsite is not a backup. Check R2 credentials and bucket name."

rm -f "${R2_CRED_FILE}"
trap - EXIT

log "Upload complete: ${R2_DEST}"

# ── 7. Local retention ───────────────────────────────────────────────────────

LOCAL_RETENTION_DAYS="${LOCAL_RETENTION_DAYS:-7}"
log "Pruning local backup dirs older than ${LOCAL_RETENTION_DAYS} days ..."
find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d \
  -mtime "+${LOCAL_RETENTION_DAYS}" \
  -exec rm -rf {} + \
  && log "Local prune done."

# ── 7b. Local disk-usage cap ─────────────────────────────────────────────────
# Hard ceiling on local backup storage so the daily dumps can never fill the
# shared disk: keep the local backup dir under MAX_LOCAL_PCT% of total disk,
# deleting oldest-first. R2 holds the long-term (7-yr) copies, so trimming local
# history here is safe. The newest backup is always kept.
MAX_LOCAL_PCT="${MAX_LOCAL_PCT:-10}"
TOTAL_BYTES="$(df -B1 --output=size "${BACKUP_DIR}" | tail -1 | tr -d '[:space:]')"
CAP_BYTES=$(( TOTAL_BYTES * MAX_LOCAL_PCT / 100 ))
log "Local cap: ${MAX_LOCAL_PCT}% of $(( TOTAL_BYTES/1024/1024/1024 ))GB disk = $(( CAP_BYTES/1024/1024 ))MB ..."
while true; do
  CUR_BYTES="$(du -sb "${BACKUP_DIR}" 2>/dev/null | cut -f1)"
  N_DIRS="$(find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d | wc -l)"
  if (( CUR_BYTES <= CAP_BYTES )); then break; fi
  if (( N_DIRS <= 1 )); then
    log "WARNING: newest backup alone ($(( CUR_BYTES/1024/1024 ))MB) exceeds the ${MAX_LOCAL_PCT}% cap; keeping it."
    break
  fi
  OLDEST="$(find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
            | sort -n | head -1 | cut -d' ' -f2-)"
  log "  over cap ($(( CUR_BYTES/1024/1024 ))MB > $(( CAP_BYTES/1024/1024 ))MB) — removing oldest: ${OLDEST}"
  rm -rf "${OLDEST}"
done
log "Local cap enforced."

# Note: R2 long-term retention (7 years, for the SEBI ai_recommendation_audit trail)
# is managed by an R2 lifecycle rule on the bucket — not by this script.
# See docs/ops/backup-restore-runbook.md for the lifecycle rule configuration.

# ── 8. Success summary ───────────────────────────────────────────────────────

log "=== Backup SUCCESS: stamp=${UTC_STAMP} git=${GIT_SHA} alembic=${ALEMBIC_REV} r2_dest=${R2_DEST} ==="
