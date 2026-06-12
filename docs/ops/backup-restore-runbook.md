# DhanRadar — Backup and Restore Runbook (B37)

## Purpose and data-residency requirement

This runbook covers nightly backup of the DhanRadar TimescaleDB Postgres database and
Redis instance to Cloudflare R2 (target: India-resident — see the verified-state note
below), plus the verified restore procedure.

**Data-residency is a hard requirement.** The backup bucket MUST be created with
`"jurisdiction": "in"` (Cloudflare India region). This satisfies:

- **DPDP** — personal data (`user_id` and related rows) must not leave India.
- **SEBI 7-year audit trail** — the `ai_recommendation_audit` table records every AI label
  served to every user; SEBI regulations require this trail to be retained for 7 years.

The bucket jurisdiction cannot be changed after creation. See
[docs/ops/b25-b34-infra-verification.md](b25-b34-infra-verification.md) for the exact
verification steps and Cloudflare API call to create a correctly scoped bucket.

**Verified state (2026-06-12):** `get-bucket-location` returned an APAC hint. Cloudflare
R2 currently offers no India jurisdiction option (available jurisdictions: EU, FedRAMP only).
The `"jurisdiction": "in"` requirement above is not yet satisfiable as-written. An
operator/counsel decision is required under **B34** before compliance-archival or backups
of user data are declared residency-compliant. Do NOT delete or soften the requirement
above — it remains the target; only the verification status is being annotated here.
The decision to run nightly backups before residency is verified was made 2026-06-12 (the
B37 escalation: "wire the cron NOW" after the SEV1 total-data-loss event) — a deliberate
risk acceptance that data-loss risk outweighs the unresolved residency question, pending
formal operator/counsel review under B34.

---

## What is backed up

### Postgres (primary, mandatory)

All schemas in the `dhanradar` database are captured by a nightly `pg_dump -Fc`
(custom format, compressed). This includes:

- `auth.*` — users, sessions, refresh tokens
- `scoring.*` — rating engine outputs, ranking configs
- `ai_recommendation_audit` — the SEBI-required 7-year AI label trail
- `compliance.*` — disclaimer versions, consent records
- All TimescaleDB hypertables and continuous aggregates

The nightly logical `pg_dump` is the **launch minimum**. It gives a recovery-point objective
(RPO) of up to 24 hours. For a tighter RPO, the recommended next tier is continuous WAL
archival with point-in-time recovery (PITR):

```text
# Future: WAL archival to R2 via pgBackRest or postgres archive_command
# Sketch:
#   archive_command = 'aws s3 cp %p s3://$R2_BACKUP_BUCKET/wal/%f --endpoint-url $R2_ENDPOINT'
#   restore_command = 'aws s3 cp s3://$R2_BACKUP_BUCKET/wal/%f %p --endpoint-url $R2_ENDPOINT'
# This is not implemented at launch. Track as a post-launch hardening item.
```

### Redis (best-effort)

Redis holds application caches and the Celery task queue. It is **regenerable** — caches
rebuild on demand and tasks re-enqueue on worker restart. The backup captures:

- `dump.rdb` — the point-in-time RDB snapshot (triggered by `BGSAVE` before copy)
- `redis-appendonly.tar.gz` — the full `/data` directory including the AOF log

Redis restore is best-effort. A Redis loss is operationally disruptive but not a data-loss
event for user or audit data.

---

## Schedule

The KVM4 host crontab entry is **installed and verified** (2026-06-12). Run as the user
owning the repo checkout:

```cron
30 21 * * * cd <DHANRADAR-REPO-PATH> && PATH=<DHANRADAR-TOOLS>/bin:/usr/bin:/bin flock -n /var/lock/dhanradar-backup.lock bash scripts/backup.sh >> /var/log/dhanradar-backup.log 2>&1
```

`21:30 UTC` = `03:00 IST` — chosen so the backup runs after the two nightly compliance beat
jobs: `archive_audit_daily` at `02:00 IST` and `reconcile_audit_disclaimers` at `02:30 IST`.
This ensures the audit trail written by those jobs is included in the same nightly snapshot.

The `flock -n` guard prevents a second backup from starting if a prior run is still in
progress (e.g. a slow R2 upload on a large dump). If the lock is held the new invocation
exits immediately and logs nothing — check `/var/log/dhanradar-backup.log` if a run appears
to have been skipped.

The `aws` CLI (v2) used by `backup.sh` lives in a DhanRadar-scoped tools directory outside
the repo checkout. Its real path is in `docs/infra-notes.md` (local-only, never committed).
The `PATH=<DHANRADAR-TOOLS>/bin:…` prefix in the cron line makes it available without
modifying the system PATH. Replace `<DHANRADAR-REPO-PATH>` and `<DHANRADAR-TOOLS>` with
the real values from `docs/infra-notes.md`.

Alternatively, use a systemd timer for more robust failure handling and logging:

```ini
# /etc/systemd/system/dhanradar-backup.timer
[Unit]
Description=DhanRadar nightly backup timer

[Timer]
OnCalendar=*-*-* 21:30:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/dhanradar-backup.service
[Unit]
Description=DhanRadar nightly backup
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/path/to/dhanradar
ExecStart=/bin/bash scripts/backup.sh
StandardOutput=journal
StandardError=journal
```

Enable with: `systemctl enable --now dhanradar-backup.timer`

---

## Storage and residency

### Object prefix layout

Backups are uploaded under the `backups/<UTC_STAMP>/` prefix inside the R2 bucket, e.g.:

```
backups/20260612171924/db.dump
backups/20260612171924/redis-dump.rdb
backups/20260612171924/redis-appendonly.tar.gz
backups/20260612171924/MANIFEST
```

The bucket is shared with other app assets. Using a `backups/` prefix keeps backup objects
in a distinct namespace so the lifecycle rule (see below) can be scoped to `backups/` only
and can never accidentally expire app assets.

**Legacy note:** one root-level backup exists from the pre-prefix era (stamp
`20260611111632`). It is NOT addressable via the current `restore.sh` R2 path form (which
now prepends `backups/`). It can still be restored using `restore.sh`'s local-path form if
the corresponding directory exists under `/var/backups/dhanradar/` on the KVM4 host:

```bash
CONFIRM_RESTORE=1 bash scripts/restore.sh /var/backups/dhanradar/20260611111632
```

### R2 bucket requirements

- **Jurisdiction**: `"in"` (India). See residency note in the Purpose section above and
  B34 for the current verified state.
- **Lifecycle rule — 7-year retention for audit trail**: Configure an R2 lifecycle rule to
  retain objects for at least 7 years (≥ 2,557 days), scoped to the `backups/` prefix
  **only**. This is an operator action in the Cloudflare dashboard; the S3 API token
  (Object Read & Write only) gets `AccessDenied` on `GetBucketLifecycleConfiguration` /
  `PutBucketLifecycleConfiguration` — verified 2026-06-12. The rule must be set manually
  by an operator with account-level R2 admin access.

  **Important:** with no expiration rule in place, objects are retained indefinitely.
  Indefinite retention satisfies the ≥ 7-year floor — the lifecycle rule is cost hygiene
  (pruning very old backups), not the compliance control. Until the rule is set, the
  retention requirement is met by the absence of any expiration, not violated by it.

  Scope the rule to prefix `backups/` **only** — never to the whole bucket, which would
  risk expiring app assets stored at other prefixes.

Example lifecycle rule (operator runs this in the Cloudflare dashboard or via an
account-admin token — NOT the backup script's Object Read & Write token):

```bash
curl -s -X PUT \
  "https://api.cloudflare.com/client/v4/accounts/${R2_ACCOUNT_ID}/r2/buckets/${R2_BACKUP_BUCKET}/lifecycle" \
  -H "Authorization: Bearer <R2_ADMIN_API_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "rules": [{
      "id": "7yr-audit-retention",
      "status": "Enabled",
      "filter": { "prefix": "backups/" },
      "expiration": { "days": 2557 }
    }]
  }'
```

### Least-privilege R2 token

Create a dedicated R2 API token with **object read and write only** on the backup bucket —
not account-level admin. This limits blast radius if the token is ever rotated or leaked.

In the Cloudflare dashboard: R2 → Manage R2 API tokens → Create API Token →
Permissions: Object Read & Write → Bucket: `<backup bucket only>`.

### Local retention

The backup script retains local copies for `LOCAL_RETENTION_DAYS` (default 7 days) and
then prunes them. Local copies are under `/var/backups/dhanradar/` on the KVM4 host —
this absolute host path is outside the repository and is never committed.

---

## Required environment variables

All secrets come from the root `.env` file (gitignored). Never commit secrets.

| Variable | Description |
|---|---|
| `POSTGRES_PASSWORD` | Postgres superuser password |
| `R2_ACCOUNT_ID` | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | R2 API token key ID |
| `R2_SECRET_ACCESS_KEY` | R2 API token secret |
| `R2_BACKUP_BUCKET` | Name of the backup bucket (target: India-resident per B34 — residency not yet verified; see the Purpose section) |
| `R2_ENDPOINT` | `https://<account-id>.r2.cloudflarestorage.com` |

Optional overrides (set before calling the script):

| Variable | Default | Description |
|---|---|---|
| `BACKUP_DIR` | `/var/backups/dhanradar` | Local staging directory |
| `LOCAL_RETENTION_DAYS` | `7` | Days to keep local backup dirs |

---

## Running a restore

### Prerequisites

- Identify the backup to restore. List available R2 prefixes:

```bash
AWS_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID}" \
AWS_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY}" \
  aws s3 ls "s3://${R2_BACKUP_BUCKET}/" \
    --endpoint-url "${R2_ENDPOINT}"
```

- Confirm the application is in a maintenance window or taken offline before restoring.
  Restoring into a live database risks data inconsistency.

### TimescaleDB restore wrappers

`restore.sh` wraps `pg_restore` in `timescaledb_pre_restore()` / `timescaledb_post_restore()`
calls. This is required for TimescaleDB databases: without these wrappers the hypertable
chunk catalog restore fails. The `post_restore` call runs unconditionally even when
`pg_restore` exits non-zero — if it were skipped after a failed restore the database would
be left with `timescaledb.restoring=on` and would be unusable. The quarterly restore drill
(see below) exercises this exact sequence end-to-end and proved it works (2026-06-12).

### Invocation

```bash
CONFIRM_RESTORE=1 bash scripts/restore.sh <backup-stamp>
```

Where `<backup-stamp>` is the UTC timestamp directory name from R2, e.g. `20260612171924`.
The script fetches from the `backups/<stamp>/` prefix automatically.

To restore from a local backup dir already on disk:

```bash
CONFIRM_RESTORE=1 bash scripts/restore.sh /var/backups/dhanradar/20260607194500
```

The `CONFIRM_RESTORE=1` variable is a mandatory safety gate. Omitting it aborts the script
with a loud warning before touching any data.

### Full clean restore (preferred for major recovery)

For a guaranteed clean state — especially when recovering after schema corruption — drop
and recreate the target database before running `pg_restore`:

```bash
# 1. Drop and recreate the database (requires a superuser or the dhanradar user with CREATEDB).
docker compose exec -T dhanradar-postgres \
  psql -U dhanradar -d postgres \
  -c "DROP DATABASE IF EXISTS dhanradar; CREATE DATABASE dhanradar OWNER dhanradar;"

# 2. Then run restore.sh — pg_restore will restore into the fresh empty database.
CONFIRM_RESTORE=1 bash scripts/restore.sh <prefix>
```

---

## Verification after restore

Run these checks before declaring the restore successful and returning the service to traffic.

### 1. Alembic schema version

```bash
docker compose run --rm dhanradar-fastapi alembic current
# Must match the code head (the revision in the MANIFEST).
# If it does not match (backup is older than current migrations), run:
docker compose run --rm dhanradar-fastapi alembic upgrade head
```

### 2. Row-count spot checks

```bash
# User count — confirm users table is non-empty (or matches expected count).
docker compose exec -T dhanradar-postgres \
  psql -U dhanradar -d dhanradar \
  -c "SELECT COUNT(*) AS user_count FROM auth.users;"

# Audit trail — confirm the SEBI compliance table is present and non-empty.
docker compose exec -T dhanradar-postgres \
  psql -U dhanradar -d dhanradar \
  -c "SELECT COUNT(*) AS audit_rows FROM ai_recommendation_audit;"
```

### 3. Application health

```bash
# Bring the full stack up and confirm health checks pass.
docker compose up -d
docker compose ps
# All services should show "healthy" within ~90s.
```

### 4. Redis

Redis rebuilds automatically. If the restore included Redis data, confirm the service is up:

```bash
docker compose exec -T dhanradar-redis redis-cli ping
# Expected: PONG
```

---

## Restore drill (quarterly, mandatory)

**An untested backup is not a backup.**

Run a full restore drill every quarter from the repo root:

```bash
bash scripts/restore-drill.sh [<backup-stamp>]
```

The script automates the complete isolated-project flow: it spins up a `dhanradar-drill`
Compose project, fetches the backup from R2, verifies the MANIFEST sha256, runs the
`timescaledb_pre_restore` / `pg_restore` / `timescaledb_post_restore` sequence, checks
the alembic revision and row counts, measures timings, and tears down the drill stack on
success. It is non-destructive — the production stack is never touched.

Log the drill outcome in `docs/ops/restore-drill-log.md` (one fenced record per drill;
see that file for the record format and the first PASS entry from 2026-06-12).

---

## RPO / RTO statement (B37, drill-backed)

**RPO: ≤ 24 hours.** The nightly cron at 21:30 UTC sets the maximum data-loss window to
one day. A failure of the cron job (check `/var/log/dhanradar-backup.log`) can extend this
window — backup-failure alerting is a residual item (B37-f1).

**RTO: drill-measured 28–44 seconds end-to-end** for a 43.6 MB dump (5,954,403 NAV rows,
41 audit rows, 6 auth users) — two runs on 2026-06-12 (the 44 s run used the shipping
hardened scripts; per-object fetches add ~17 s vs the recursive copy). Restore portion is
~17–18 s in both (scratch-pg start + timescaledb_pre_restore + pg_restore + post_restore).

**Stated production RTO: ≤ 15 minutes**, accounting for app stop/start, operator reaction
time, and post-restore verification before returning to traffic. This is a conservative
estimate based on the drill timing plus operational overhead.

RTO must be re-derived if database size grows materially (e.g. after equities/ETF data
ingestion). The drill-measured 28 s is the restore-only lower bound at current size.
WAL archival with point-in-time recovery (PITR) remains the planned next tier for a tighter
RPO; see the WAL sketch in the "What is backed up" section.

---

## Alternative upload tool (rclone)

The scripts use the `aws` CLI with `--endpoint-url` because R2 speaks the S3 protocol and
the AWS CLI is widely available on Linux without additional setup. If `rclone` is preferred:

```bash
# rclone config equivalent:
# [r2]
# type = s3
# provider = Cloudflare
# access_key_id = <R2_ACCESS_KEY_ID>
# secret_access_key = <R2_SECRET_ACCESS_KEY>
# endpoint = https://<account-id>.r2.cloudflarestorage.com

rclone copy "${WORK_DIR}/" "r2:${R2_BACKUP_BUCKET}/${UTC_STAMP}/" --progress
```

rclone supports parallel multi-part uploads and can be faster for large dumps. The `aws` CLI
path (single-part for files under 8 MB, auto-multi-part above) is sufficient for the
expected dump sizes at launch.
