#!/usr/bin/env bash
# scripts/restore-db.sh — Restore a DhanRadar Postgres backup from R2.
#
# Why this script exists: a naive `pg_restore` SILENTLY LOSES TimescaleDB
# hypertable data (e.g. all ~6M mf.mf_nav_history rows) — the regular tables come
# back and it looks like it worked. TimescaleDB requires a pre_restore/post_restore
# wrap. This script does that correctly, and decrypts the age-encrypted artifacts.
#
# USAGE
#   bash scripts/restore-db.sh [STAMP|latest] [TARGET_DB]
#     STAMP     : R2 backup stamp (YYYYMMDDHHMMSS) or "latest" (default).
#     TARGET_DB : DB to restore into (default: dhanradar_restore_test).
#
#   DRILL=1 (default): verify row counts vs prod, then DROP the target DB (a safe
#                      restore-test). DRILL=0: keep the restored DB (real recovery).
#
# REQUIREMENTS: run from repo root; .env present; aws CLI + docker compose + age;
#   age identity at /etc/dhanradar-keys/backup_age.key (the OFFLINE-backed-up key).
#
# SECRETS: loads .env but never prints secret values.
set -euo pipefail

TIMESTAMP() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
log()  { echo "[$(TIMESTAMP)] $*"; }
die()  { echo "[$(TIMESTAMP)] ERROR: $*" >&2; exit 1; }
warn() { echo "[$(TIMESTAMP)] WARNING: $*" >&2; }

STAMP="${1:-latest}"
TARGET_DB="${2:-dhanradar_restore_test}"
DRILL="${DRILL:-1}"
PG_SVC="dhanradar-postgres"
AGE_IDENTITY="${AGE_IDENTITY:-/etc/dhanradar-keys/backup_age.key}"

[[ -f docker-compose.yml ]] || die "run from the repo root (docker-compose.yml not found)."
[[ -f .env ]] || die ".env not found."
command -v aws  >/dev/null 2>&1 || die "'aws' CLI not found on PATH."
command -v age  >/dev/null 2>&1 || die "'age' not found on PATH."
docker compose version >/dev/null 2>&1 || die "'docker compose' v2 not available."

if [[ "${DRILL}" == "0" && "${TARGET_DB}" == "dhanradar" ]]; then
  die "refusing to restore over the live 'dhanradar' DB. Restore into a new DB, verify, then promote manually."
fi

_env_get() { grep -E "^$1=" .env | head -1 | cut -d= -f2- | tr -d '\r'; }
export AWS_ACCESS_KEY_ID="$(_env_get R2_ACCESS_KEY_ID)"
export AWS_SECRET_ACCESS_KEY="$(_env_get R2_SECRET_ACCESS_KEY)"
R2_ENDPOINT="$(_env_get R2_ENDPOINT)"
R2_BUCKET="$(_env_get R2_BACKUP_BUCKET)"
[[ -n "${AWS_ACCESS_KEY_ID}" && -n "${R2_ENDPOINT}" && -n "${R2_BUCKET}" ]] \
  || die "R2 credentials/endpoint/bucket missing from .env."

# ── Resolve the stamp ────────────────────────────────────────────────────────
if [[ "${STAMP}" == "latest" ]]; then
  STAMP="$(aws s3 ls --endpoint-url "${R2_ENDPOINT}" "s3://${R2_BUCKET}/backups/" \
           | awk '{print $2}' | tr -d / | grep -E '^[0-9]{14}$' | sort | tail -1)"
  [[ -n "${STAMP}" ]] || die "could not resolve latest backup stamp from R2."
fi
log "Restoring backup stamp=${STAMP} into DB=${TARGET_DB} (DRILL=${DRILL})"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# ── Download db dump (encrypted preferred, legacy plaintext fallback) ─────────
SRC_ENC="s3://${R2_BUCKET}/backups/${STAMP}/db.dump.age"
SRC_PLAIN="s3://${R2_BUCKET}/backups/${STAMP}/db.dump"
if aws s3 ls --endpoint-url "${R2_ENDPOINT}" "${SRC_ENC}" >/dev/null 2>&1; then
  log "Downloading ${SRC_ENC} ..."
  aws s3 cp --endpoint-url "${R2_ENDPOINT}" "${SRC_ENC}" "${WORK}/db.dump.age" --no-progress
  [[ -f "${AGE_IDENTITY}" ]] || die "age identity ${AGE_IDENTITY} not found — cannot decrypt."
  log "Decrypting with age ..."
  age -d -i "${AGE_IDENTITY}" -o "${WORK}/db.dump" "${WORK}/db.dump.age" \
    || die "age decryption failed (wrong identity key?)."
elif aws s3 ls --endpoint-url "${R2_ENDPOINT}" "${SRC_PLAIN}" >/dev/null 2>&1; then
  log "Downloading legacy unencrypted ${SRC_PLAIN} ..."
  aws s3 cp --endpoint-url "${R2_ENDPOINT}" "${SRC_PLAIN}" "${WORK}/db.dump" --no-progress
else
  die "no db.dump(.age) found under backups/${STAMP}/ in R2."
fi
log "Dump ready ($(du -h "${WORK}/db.dump" | cut -f1))."

# ── Resolve the TimescaleDB version to pin (B37) ─────────────────────────────
# TSDB_VERSION env overrides; else read timescaledb_version= from the backup's
# MANIFEST (fetched here — this script otherwise only downloads db.dump).
SRC_MANIFEST="s3://${R2_BUCKET}/backups/${STAMP}/MANIFEST"
TSDB_VERSION_SRC="unpinned"
if [[ -n "${TSDB_VERSION:-}" ]]; then
  TSDB_VERSION_SRC="env"
elif aws s3 cp --endpoint-url "${R2_ENDPOINT}" "${SRC_MANIFEST}" "${WORK}/MANIFEST" --no-progress >/dev/null 2>&1; then
  TSDB_VERSION="$(grep '^timescaledb_version=' "${WORK}/MANIFEST" | cut -d= -f2 || true)"
  [[ -n "${TSDB_VERSION}" && "${TSDB_VERSION}" != "unavailable" ]] && TSDB_VERSION_SRC="manifest" || TSDB_VERSION=""
else
  warn "MANIFEST not found under backups/${STAMP}/ — cannot resolve timescaledb_version from it."
fi
if [[ -n "${TSDB_VERSION:-}" ]]; then
  [[ "${TSDB_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
    || die "timescaledb version '${TSDB_VERSION}' (source: ${TSDB_VERSION_SRC}) is not a valid x.y.z — refusing to use it in SQL."
  log "TimescaleDB target version: ${TSDB_VERSION} (source: ${TSDB_VERSION_SRC})"
else
  warn "No timescaledb_version resolved — TARGET_DB will get the image's DEFAULT timescaledb version, which may differ from the dump's."
fi

# ── Recreate target DB ───────────────────────────────────────────────────────
log "(Re)creating target DB ${TARGET_DB} ..."
docker compose exec -T "${PG_SVC}" dropdb   -U dhanradar --if-exists "${TARGET_DB}"
docker compose exec -T "${PG_SVC}" createdb -U dhanradar "${TARGET_DB}"

# ── TimescaleDB-aware restore (the whole point of this script) ───────────────
# TARGET_DB was JUST created fresh above (drop --if-exists + createdb, always,
# every run) — it can never contain the extension or any data yet, so pinning
# here needs no non-empty guard (contrast restore-drill.sh, whose scratch DB
# can in principle survive across runs if a prior drill's teardown was skipped).
if [[ -n "${TSDB_VERSION:-}" ]]; then
  AVAILABLE="$(docker compose exec -T "${PG_SVC}" psql -U dhanradar -d "${TARGET_DB}" -tAc \
    "SELECT 1 FROM pg_available_extension_versions WHERE name='timescaledb' AND version='${TSDB_VERSION}';" \
    2>/dev/null | tr -d '[:space:]')"
  [[ "${AVAILABLE}" == "1" ]] \
    || die "timescaledb ${TSDB_VERSION} is not in this image's pg_available_extension_versions — refusing."
  log "CREATE EXTENSION timescaledb VERSION '${TSDB_VERSION}' + timescaledb_pre_restore() ..."
  docker compose exec -T "${PG_SVC}" psql -U dhanradar -d "${TARGET_DB}" -v ON_ERROR_STOP=1 \
    -qc "CREATE EXTENSION timescaledb VERSION '${TSDB_VERSION}';" \
    || die "Failed to create timescaledb extension at version ${TSDB_VERSION}."
else
  log "CREATE EXTENSION timescaledb (unpinned, image default) + timescaledb_pre_restore() ..."
  docker compose exec -T "${PG_SVC}" psql -U dhanradar -d "${TARGET_DB}" -qc "CREATE EXTENSION IF NOT EXISTS timescaledb;"
fi
docker compose exec -T "${PG_SVC}" psql -U dhanradar -d "${TARGET_DB}" -tAqc "SELECT timescaledb_pre_restore();"

log "pg_restore (errors for pg_cron / timescale catalog tables are expected/benign) ..."
set +e
docker compose exec -T "${PG_SVC}" pg_restore -U dhanradar -d "${TARGET_DB}" --no-owner --no-acl \
  < "${WORK}/db.dump" 2> "${WORK}/restore.err"
set -e

log "timescaledb_post_restore() ..."
docker compose exec -T "${PG_SVC}" psql -U dhanradar -d "${TARGET_DB}" -tAqc "SELECT timescaledb_post_restore();" || true

# ── Re-apply erasures (DPDP: erased people must never come back) ────────────
# IDs = the newest backup's erased_ids.txt.age (a fresh download — independent
# of the stamp actually being restored, since an old restore should still
# honor every erasure known since) UNION the LIVE dhanradar DB's own
# admin_actions, when live is reachable and isn't this restore's target.
# See backend/dhanradar/compliance/data_policy.py + scripts/backup.sh §4a.
log "Resolving erased-user ids to re-apply into ${TARGET_DB} ..."
ERASE_TMP="${WORK}/erased_ids_merged.txt"
: > "${ERASE_TMP}"

LATEST_STAMP="$(aws s3 ls --endpoint-url "${R2_ENDPOINT}" "s3://${R2_BUCKET}/backups/" \
  | awk '{print $2}' | tr -d / | grep -E '^[0-9]{14}$' | sort | tail -1 || true)"
if [[ -n "${LATEST_STAMP}" ]] && aws s3 ls --endpoint-url "${R2_ENDPOINT}" \
    "s3://${R2_BUCKET}/backups/${LATEST_STAMP}/erased_ids.txt.age" >/dev/null 2>&1; then
  log "Downloading erased_ids.txt.age from newest backup stamp=${LATEST_STAMP} ..."
  aws s3 cp --endpoint-url "${R2_ENDPOINT}" \
    "s3://${R2_BUCKET}/backups/${LATEST_STAMP}/erased_ids.txt.age" \
    "${WORK}/erased_ids.txt.age" --no-progress
  if [[ -f "${AGE_IDENTITY}" ]]; then
    age -d -i "${AGE_IDENTITY}" -o "${WORK}/erased_ids.txt" "${WORK}/erased_ids.txt.age" \
      && cat "${WORK}/erased_ids.txt" >> "${ERASE_TMP}" \
      || warn "Could not decrypt erased_ids.txt.age from backup stamp=${LATEST_STAMP} — continuing without it."
  else
    warn "age identity ${AGE_IDENTITY} not found — cannot decrypt erased_ids.txt.age."
  fi
else
  warn "No erased_ids.txt.age found under the newest backup (stamp=${LATEST_STAMP:-none}, likely an older backup) — continuing without it."
fi

if [[ "${TARGET_DB}" != "dhanradar" ]] && docker compose exec -T "${PG_SVC}" \
    psql -U dhanradar -d dhanradar -tAc "SELECT 1;" >/dev/null 2>&1; then
  log "Live 'dhanradar' DB reachable — adding its erased-user ids too ..."
  docker compose exec -T "${PG_SVC}" psql -U dhanradar -d dhanradar -tAc \
    "SELECT DISTINCT target_id FROM audit.admin_actions WHERE action = 'erase_user' AND target_id IS NOT NULL ORDER BY 1;" \
    >> "${ERASE_TMP}" || warn "Could not query live admin_actions for erased ids — continuing with the backup-derived list only."
else
  log "Live DB not reachable, or restore target IS 'dhanradar' — using the backup-derived erasure list only."
fi

sort -u -o "${ERASE_TMP}" "${ERASE_TMP}"
if [[ -s "${ERASE_TMP}" ]]; then
  ERASE_COUNT="$(grep -c . "${ERASE_TMP}")"
  log "Re-applying ${ERASE_COUNT} erasure(s) into ${TARGET_DB} via erasure_cli ..."
  if docker compose run --rm -T dhanradar-fastapi \
      python -m dhanradar.auth.erasure_cli --database "${TARGET_DB}" --ids-file - < "${ERASE_TMP}"; then
    log "Erasure re-apply completed for ${TARGET_DB}."
  else
    die "erasure_cli FAILED for ${TARGET_DB} — the restored database may contain erased people. Do not serve traffic from it until this is fixed."
  fi
else
  warn "No erased-user ids available from any source — skipping re-apply. If erasures exist, apply them manually before use."
fi

# ── Verify ───────────────────────────────────────────────────────────────────
_count() { docker compose exec -T "${PG_SVC}" psql -U dhanradar -d "$1" -tAc "SELECT count(*) FROM $2" 2>/dev/null | tr -d '[:space:]'; }
NAV_R="$(_count "${TARGET_DB}" mf.mf_nav_history || echo ERR)"
NAV_P="$(_count dhanradar       mf.mf_nav_history || echo ERR)"
USR_R="$(_count "${TARGET_DB}" auth.users || echo ERR)"
USR_P="$(_count dhanradar       auth.users || echo ERR)"
log "VERIFY mf.mf_nav_history: restored=${NAV_R} prod=${NAV_P}"
log "VERIFY auth.users       : restored=${USR_R} prod=${USR_P}"

OK=1
[[ "${NAV_R}" == "${NAV_P}" && "${NAV_R}" != "ERR" ]] || OK=0
[[ "${USR_R}" == "${USR_P}" && "${USR_R}" != "ERR" ]] || OK=0

if [[ "${DRILL}" == "1" ]]; then
  log "DRILL: dropping ${TARGET_DB} ..."
  docker compose exec -T "${PG_SVC}" dropdb -U dhanradar --if-exists "${TARGET_DB}"
fi

if (( OK == 1 )); then
  log "=== RESTORE VERIFIED OK (stamp=${STAMP}) ==="
else
  die "RESTORE VERIFICATION FAILED — counts mismatch (see above). stderr: $(tail -3 "${WORK}/restore.err" 2>/dev/null)"
fi