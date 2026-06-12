#!/usr/bin/env bash
# scripts/restore-drill.sh — Quarterly restore drill into an ISOLATED scratch
# stack (B37). Non-destructive: never touches the live `dhanradar` compose
# project. Restores the chosen (default: latest) R2 backup into a throwaway
# `dhanradar-drill` postgres, verifies it, measures restore time (the RTO
# input), and tears the scratch stack down.
#
# USAGE
#   bash scripts/restore-drill.sh [<backup-prefix>]
#
#   <backup-prefix> is a UTC stamp under backups/ (e.g. 20260612031500), an
#   explicit R2 prefix containing "/", or a local backup directory path.
#   With no argument the latest backups/ stamp in R2 is used.
#
# REQUIREMENTS
#   Same as backup.sh: repo root, .env, `aws` CLI, Docker Compose v2.
#
# SAFETY
#   - All docker ops are scoped to project `dhanradar-drill` — a fresh, isolated
#     project (own network, own volumes). The live stack is never referenced.
#   - On SUCCESS the scratch stack is removed (down -v). On FAILURE it is left
#     up for diagnosis and the teardown command is printed.
#
# SECRETS: this script loads .env but NEVER prints secret values.
#
set -euo pipefail

# ── Helpers ──────────────────────────────────────────────────────────────────

TIMESTAMP() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
log()  { echo "[$(TIMESTAMP)] $*"; }
die()  { echo "[$(TIMESTAMP)] ERROR: $*" >&2; exit 1; }
warn() { echo "[$(TIMESTAMP)] WARNING: $*" >&2; }

DRILL_PROJECT="dhanradar-drill"
DC="docker compose -p ${DRILL_PROJECT} -f docker-compose.yml"

# ── 1. Preconditions ─────────────────────────────────────────────────────────

log "=== DhanRadar restore DRILL started (project: ${DRILL_PROJECT}) ==="

[[ -f "docker-compose.yml" ]] || die "docker-compose.yml not found. Run from the repo root."
[[ -f ".env" ]]               || die ".env not found at repo root."

# Load ONLY needed vars (never `source` .env — multi-line PEM breaks bash).
_env_get() { grep -E "^$1=" .env | head -1 | cut -d= -f2-; }
POSTGRES_PASSWORD="$(_env_get POSTGRES_PASSWORD)"
R2_ACCESS_KEY_ID="$(_env_get R2_ACCESS_KEY_ID)"
R2_SECRET_ACCESS_KEY="$(_env_get R2_SECRET_ACCESS_KEY)"
R2_BACKUP_BUCKET="$(_env_get R2_BACKUP_BUCKET)"
R2_ENDPOINT="$(_env_get R2_ENDPOINT)"

_assert_var() {
  local name="$1"; local val="${!name:-}"
  [[ -n "${val}" ]] || die "Required variable ${name} is not set or is empty in .env"
}
_assert_var POSTGRES_PASSWORD

command -v aws    > /dev/null 2>&1 || die "'aws' CLI not found on PATH."
command -v docker > /dev/null 2>&1 || die "'docker' not found on PATH."
docker compose version > /dev/null 2>&1 || die "'docker compose' (v2) not available."

# Refuse to run over an existing drill stack (stale state would corrupt timing).
if [[ -n "$(${DC} ps -q 2>/dev/null)" ]]; then
  die "A ${DRILL_PROJECT} stack is already running. Tear it down first: ${DC} down -v"
fi

# ── 2. Resolve + fetch the backup ────────────────────────────────────────────

_r2_cred_file() {
  # Trap registered BEFORE the secret is written — no failure window leaks it.
  R2_CRED_FILE="$(mktemp)"
  trap 'rm -f "${R2_CRED_FILE}"' EXIT
  chmod 600 "${R2_CRED_FILE}"
  printf '[default]\naws_access_key_id=%s\naws_secret_access_key=%s\n' \
    "${R2_ACCESS_KEY_ID}" "${R2_SECRET_ACCESS_KEY}" > "${R2_CRED_FILE}"
}

BACKUP_ARG="${1:-}"
RESTORE_DIR=""
T_FETCH_START=$(date +%s)

if [[ -n "${BACKUP_ARG}" && ( "${BACKUP_ARG}" == /* || "${BACKUP_ARG}" == .* || "${BACKUP_ARG}" == ~* ) ]]; then
  RESTORE_DIR="${BACKUP_ARG}"
  [[ -d "${RESTORE_DIR}" ]] || die "Local backup directory not found: ${RESTORE_DIR}"
  log "Using local backup dir: ${RESTORE_DIR}"
else
  _assert_var R2_ACCESS_KEY_ID
  _assert_var R2_SECRET_ACCESS_KEY
  _assert_var R2_BACKUP_BUCKET
  _assert_var R2_ENDPOINT
  _r2_cred_file

  if [[ -z "${BACKUP_ARG}" ]]; then
    # Latest stamp under backups/ (prefixes sort lexicographically = chronologically).
    BACKUP_ARG="$(AWS_SHARED_CREDENTIALS_FILE="${R2_CRED_FILE}" AWS_PROFILE=default \
      aws s3 ls "s3://${R2_BACKUP_BUCKET}/backups/" --endpoint-url "${R2_ENDPOINT}" \
      | awk '/PRE/ {print $2}' | tr -d '/' | sort | tail -1)"
    [[ -n "${BACKUP_ARG}" ]] || die "No backups found under s3://<bucket>/backups/."
    # Bucket content chooses this value — constrain it to a real UTC stamp so a
    # planted prefix cannot smuggle anything else into the R2_SRC string.
    [[ "${BACKUP_ARG}" =~ ^[0-9]{14}$ ]] \
      || die "Auto-detected latest stamp '${BACKUP_ARG}' is not a 14-digit UTC stamp — refusing."
    log "Latest backup stamp: ${BACKUP_ARG}"
  fi

  BACKUP_ARG="${BACKUP_ARG%/}"
  if [[ "${BACKUP_ARG}" == */* ]]; then
    R2_SRC="s3://${R2_BACKUP_BUCKET}/${BACKUP_ARG}/"
  else
    R2_SRC="s3://${R2_BACKUP_BUCKET}/backups/${BACKUP_ARG}/"
  fi

  RESTORE_DIR="$(mktemp -d /tmp/dhanradar-drill-XXXXXX)"
  log "Downloading ${R2_SRC} → ${RESTORE_DIR} ..."
  # Fetch each artifact BY NAME — never `cp --recursive` (S3 keys may contain
  # "/" or ".."; explicit destinations make key-derived path traversal
  # impossible). Same hardening as restore.sh (Tier-B review, 2026-06-12).
  _r2_get() {
    AWS_SHARED_CREDENTIALS_FILE="${R2_CRED_FILE}" AWS_PROFILE=default \
      aws s3 cp "${R2_SRC}$1" "${RESTORE_DIR}/$1" \
        --endpoint-url "${R2_ENDPOINT}" --no-progress
  }
  _r2_get "MANIFEST" || die "R2 download failed for MANIFEST. Check prefix and credentials."
  _r2_get "db.dump"  || die "R2 download failed for db.dump. Check prefix and credentials."
  _r2_get "redis-dump.rdb"          || warn "redis-dump.rdb not fetched (may be absent at source) — continuing."
  _r2_get "redis-appendonly.tar.gz" || warn "redis-appendonly.tar.gz not fetched (may be absent at source) — continuing."
  rm -f "${R2_CRED_FILE}"
  trap - EXIT
fi
T_FETCH_END=$(date +%s)

# ── 3. Verify MANIFEST checksums (same allowlist as restore.sh) ──────────────

MANIFEST="${RESTORE_DIR}/MANIFEST"
[[ -f "${MANIFEST}" ]] || die "MANIFEST not found in backup dir: ${RESTORE_DIR}"

log "Verifying MANIFEST checksums ..."
db_dump_verified=false
while IFS= read -r line; do
  if [[ "${line}" =~ ^file=([^[:space:]]+)[[:space:]]+size=[^[:space:]]+[[:space:]]+sha256=([^[:space:]]+) ]]; then
    fname="${BASH_REMATCH[1]}"; expected_sha="${BASH_REMATCH[2]}"
    case "${fname}" in
      db.dump|redis-dump.rdb|redis-appendonly.tar.gz) ;;
      *) die "MANIFEST lists an unexpected artifact name '${fname}' — refusing (possible tampering)." ;;
    esac
    fpath="${RESTORE_DIR}/${fname}"
    if [[ "${expected_sha}" == "absent" ]]; then
      # absent = not produced at backup time; a present file under that name
      # means a crafted MANIFEST is trying to skip verification.
      [[ -f "${fpath}" ]] && die "MANIFEST marks ${fname} absent but the file IS present — refusing (possible tampering)."
      continue
    fi
    [[ -f "${fpath}" ]] || die "Artifact ${fname} listed in MANIFEST but missing from the download — refusing."
    actual_sha="$(sha256sum "${fpath}" | awk '{print $1}')"
    [[ "${actual_sha}" == "${expected_sha}" ]] \
      || die "Checksum MISMATCH for ${fname}. Backup may be corrupt."
    log "  OK  ${fname} (sha256 verified)"
    if [[ "${fname}" == "db.dump" ]]; then
      db_dump_verified=true
    fi
  fi
done < "${MANIFEST}"
# A MANIFEST with zero file= lines (or db.dump stripped) must never pass.
[[ "${db_dump_verified}" == "true" ]] \
  || die "MANIFEST contained no verified db.dump entry — refusing (empty or stripped MANIFEST; possible tampering)."

BACKUP_STAMP="$(grep '^backup_utc=' "${MANIFEST}" | cut -d= -f2 || echo "unknown")"
BACKUP_ALEMBIC="$(grep '^alembic_rev=' "${MANIFEST}" | cut -d= -f2 || echo "unknown")"
DB_DUMP="${RESTORE_DIR}/db.dump"
[[ -f "${DB_DUMP}" ]] || die "db.dump not found in restore dir."

# ── 4. Start the scratch postgres ────────────────────────────────────────────

log "Starting scratch postgres (project ${DRILL_PROJECT}, isolated volume/network) ..."
T_RESTORE_START=$(date +%s)
${DC} up -d --no-deps dhanradar-postgres \
  || die "Failed to start the drill postgres."

DRILL_CID="$(${DC} ps -q dhanradar-postgres)"
[[ -n "${DRILL_CID}" ]] || die "Drill postgres container not found."
DRILL_NAME="$(docker inspect -f '{{.Name}}' "${DRILL_CID}" | sed 's|^/||')"
# Hard safety: the container we operate on MUST belong to the drill project.
[[ "${DRILL_NAME}" == ${DRILL_PROJECT}-* ]] \
  || die "Resolved container '${DRILL_NAME}' is not in project ${DRILL_PROJECT} — refusing."
log "Drill container: ${DRILL_NAME}"

log "Waiting for drill postgres to become healthy (initdb on first boot) ..."
HEALTH_DEADLINE=$(( $(date +%s) + 180 ))
while true; do
  STATUS="$(docker inspect -f '{{.State.Health.Status}}' "${DRILL_CID}" 2>/dev/null || echo "unknown")"
  [[ "${STATUS}" == "healthy" ]] && break
  (( $(date +%s) >= HEALTH_DEADLINE )) && die "Drill postgres did not become healthy in 180s (status: ${STATUS})."
  sleep 3
done
log "Drill postgres healthy."

# ── 5. Restore into the scratch DB ───────────────────────────────────────────

log "timescaledb_pre_restore ..."
${DC} exec -T dhanradar-postgres \
  psql -U dhanradar -d dhanradar -v ON_ERROR_STOP=1 \
  -c "CREATE EXTENSION IF NOT EXISTS timescaledb; SELECT timescaledb_pre_restore();" \
  > /dev/null \
  || die "timescaledb_pre_restore failed on the drill DB."

log "pg_restore (--clean --if-exists --exit-on-error) ..."
restore_rc=0
${DC} exec -T dhanradar-postgres \
  pg_restore -U dhanradar -d dhanradar --clean --if-exists --exit-on-error \
  < "${DB_DUMP}" || restore_rc=$?

log "timescaledb_post_restore ..."
${DC} exec -T dhanradar-postgres \
  psql -U dhanradar -d dhanradar -v ON_ERROR_STOP=1 \
  -c "SELECT timescaledb_post_restore();" \
  > /dev/null \
  || warn "timescaledb_post_restore failed on the drill DB."

if (( restore_rc != 0 )); then
  echo "" >&2
  warn "pg_restore FAILED (exit ${restore_rc}). Drill stack left up for diagnosis."
  warn "Tear down when done:  ${DC} down -v"
  die  "DRILL FAILED at pg_restore."
fi
T_RESTORE_END=$(date +%s)

# ── 6. Verify the restored data ──────────────────────────────────────────────

_psql_scalar() {
  ${DC} exec -T dhanradar-postgres \
    psql -U dhanradar -d dhanradar -tA -c "$1" 2>/dev/null | tr -d '[:space:]'
}

log "Verifying restored data ..."
RESTORED_ALEMBIC="$(_psql_scalar "SELECT version_num FROM alembic_version;" || echo "MISSING")"
USERS_COUNT="$(_psql_scalar "SELECT COUNT(*) FROM auth.users;" || echo "ERR")"
AUDIT_REL="$(_psql_scalar "SELECT COALESCE(to_regclass('compliance.ai_recommendation_audit'), to_regclass('public.ai_recommendation_audit'))::text;")"
if [[ -n "${AUDIT_REL}" && "${AUDIT_REL}" != "null" ]]; then
  AUDIT_COUNT="$(_psql_scalar "SELECT COUNT(*) FROM ${AUDIT_REL};" || echo "ERR")"
else
  AUDIT_COUNT="TABLE-NOT-FOUND"
fi
NAV_COUNT="$(_psql_scalar "SELECT COUNT(*) FROM mf.mf_nav_history;" || echo "ERR")"

DRILL_PASS=true
# Enforce the alembic match only when the MANIFEST recorded a real revision
# (backups taken before the 2026-06-12 `python -m alembic` fix say "unavailable").
if [[ "${BACKUP_ALEMBIC}" =~ ^[a-f0-9]+$ ]]; then
  [[ "${RESTORED_ALEMBIC}" == "${BACKUP_ALEMBIC}" ]] || { warn "alembic mismatch: restored=${RESTORED_ALEMBIC} manifest=${BACKUP_ALEMBIC}"; DRILL_PASS=false; }
else
  warn "MANIFEST alembic_rev is '${BACKUP_ALEMBIC}' — skipping match; restored rev must still be present."
  [[ "${RESTORED_ALEMBIC}" =~ ^[a-f0-9]+$ ]] || { warn "restored alembic_version missing/invalid: ${RESTORED_ALEMBIC}"; DRILL_PASS=false; }
fi
[[ "${USERS_COUNT}" =~ ^[0-9]+$ ]] || { warn "auth.users count not numeric: ${USERS_COUNT}"; DRILL_PASS=false; }
[[ "${AUDIT_COUNT}" =~ ^[0-9]+$ ]] || { warn "audit count not numeric: ${AUDIT_COUNT}"; DRILL_PASS=false; }
[[ "${NAV_COUNT}" =~ ^[0-9]+$ && "${NAV_COUNT}" -gt 0 ]] || { warn "mf_nav_history count suspicious: ${NAV_COUNT}"; DRILL_PASS=false; }
T_VERIFY_END=$(date +%s)

# ── 7. Teardown (success path) / report ──────────────────────────────────────

if [[ "${DRILL_PASS}" == "true" ]]; then
  log "Tearing down the drill stack (down -v) ..."
  ${DC} down -v > /dev/null 2>&1 || warn "Teardown reported errors — check '${DC} ps'."
  rm -rf "${RESTORE_DIR}" 2>/dev/null || true
else
  warn "Drill verification FAILED — stack left up for diagnosis. Tear down: ${DC} down -v"
fi

FETCH_S=$(( T_FETCH_END - T_FETCH_START ))
RESTORE_S=$(( T_RESTORE_END - T_RESTORE_START ))
VERIFY_S=$(( T_VERIFY_END - T_RESTORE_END ))
TOTAL_S=$(( T_VERIFY_END - T_FETCH_START ))

echo ""
echo "=== RESTORE DRILL RECORD (paste into docs/ops/restore-drill-log.md) ==="
echo "drill_date_utc:   $(date -u '+%Y-%m-%d')"
echo "backup_stamp:     ${BACKUP_STAMP}"
echo "backup_alembic:   ${BACKUP_ALEMBIC}"
echo "restored_alembic: ${RESTORED_ALEMBIC}"
echo "auth_users:       ${USERS_COUNT}"
echo "audit_rows:       ${AUDIT_COUNT}"
echo "nav_rows:         ${NAV_COUNT}"
echo "fetch_seconds:    ${FETCH_S}"
echo "restore_seconds:  ${RESTORE_S}  (scratch-pg start + pre_restore + pg_restore + post_restore)"
echo "verify_seconds:   ${VERIFY_S}"
echo "total_seconds:    ${TOTAL_S}   (drill RTO input; prod RTO adds app stop/start ≈ +2-3 min)"
echo "result:           $([[ "${DRILL_PASS}" == "true" ]] && echo PASS || echo FAIL)"
echo "========================================================================"

[[ "${DRILL_PASS}" == "true" ]] || exit 1
log "=== Restore drill SUCCESS ==="
