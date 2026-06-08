# DhanRadar — Backup and Restore Runbook (B37)

## Purpose and data-residency requirement

This runbook covers nightly backup of the DhanRadar TimescaleDB Postgres database and
Redis instance to Cloudflare R2 (India-resident), plus the verified restore procedure.

**Data-residency is a hard requirement.** The backup bucket MUST be created with
`"jurisdiction": "in"` (Cloudflare India region). This satisfies:

- **DPDP** — personal data (`user_id` and related rows) must not leave India.
- **SEBI 7-year audit trail** — the `ai_recommendation_audit` table records every AI label
  served to every user; SEBI regulations require this trail to be retained for 7 years.

The bucket jurisdiction cannot be changed after creation. See
[docs/ops/b25-b34-infra-verification.md](b25-b34-infra-verification.md) for the exact
verification steps and Cloudflare API call to create a correctly scoped bucket.

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

Add to the KVM4 host crontab (run as the user owning the repo checkout):

```cron
15 19 * * * cd /path/to/dhanradar && bash scripts/backup.sh >> /var/log/dhanradar-backup.log 2>&1
```

`19:15 UTC` = `00:45 IST`, which is after midnight IST and well outside peak traffic.

Alternatively, use a systemd timer for more robust failure handling and logging:

```ini
# /etc/systemd/system/dhanradar-backup.timer
[Unit]
Description=DhanRadar nightly backup timer

[Timer]
OnCalendar=*-*-* 19:15:00 UTC
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

### R2 bucket requirements

- **Jurisdiction**: `"in"` (India). Verified via the Cloudflare dashboard or the API call
  documented in [docs/ops/b25-b34-infra-verification.md](b25-b34-infra-verification.md).
- **Lifecycle rule — 7-year retention for audit trail**: Configure an R2 lifecycle rule to
  retain objects in this bucket for at least 7 years (2,557 days). This is a deploy-time
  infra action in the Cloudflare dashboard; the backup script does not set lifecycle rules.

Example lifecycle rule via Cloudflare API:

```bash
curl -s -X PUT \
  "https://api.cloudflare.com/client/v4/accounts/${R2_ACCOUNT_ID}/r2/buckets/${R2_BACKUP_BUCKET}/lifecycle" \
  -H "Authorization: Bearer <R2_API_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "rules": [{
      "id": "7yr-audit-retention",
      "status": "Enabled",
      "filter": { "prefix": "" },
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
| `R2_BACKUP_BUCKET` | Name of the India-resident backup bucket |
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

### Invocation

```bash
CONFIRM_RESTORE=1 bash scripts/restore.sh <backup-prefix>
```

Where `<backup-prefix>` is the UTC timestamp directory name from R2, e.g. `20260607194500`.

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

Run a full restore drill into a scratch stack every quarter:

1. Spin up a separate Docker Compose stack with a distinct project name:
   `COMPOSE_PROJECT_NAME=dhanradar-drill docker compose up -d dhanradar-postgres dhanradar-redis`
2. Restore the most recent backup into the drill stack using `restore.sh` (point
   `COMPOSE_PROJECT_NAME=dhanradar-drill` and a matching compose override).
3. Run the verification steps above against the drill stack.
4. Tear down the drill stack: `COMPOSE_PROJECT_NAME=dhanradar-drill docker compose down -v`
5. Log the drill outcome (pass/fail, any issues) in `docs/project-state/SESSION_STATE.md`
   or a dedicated ops log.

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
