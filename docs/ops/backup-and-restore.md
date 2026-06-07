# DhanRadar — DB Backup and Restore

## 1. What is backed up and where

A nightly `pg_dump -Fc` of the full `dhanradar` Postgres database is uploaded to
Cloudflare R2 under the key:

```
backups/postgres/YYYY/MM/DD/dhanradar-<UTC-timestamp>.dump
```

The dump is in Postgres custom compressed format (restores with `pg_restore`).

It includes the 7-year `ai_recommendation_audit` trail required by the SEBI
educational-platform record-keeping obligation (ADR-0022).

Real R2 bucket name, account ID, and endpoint are in `docs/infra-notes.md`
(local-only, never committed).

## 2. Schedule

The backup runs from a **HOST cron** on the KVM4 box.
HOST cron is decoupled from app health: a container restart does not skip a backup.

Run at **21:30 UTC (03:00 IST)** — after the 02:00 IST `archive_audit_daily`
beat task and the 02:30 IST `reconcile_audit_disclaimers` beat task.

Sample crontab line (replace `<DHANRADAR-REPO-PATH>` with the real checkout path
from `docs/infra-notes.md`):

```cron
# 30 21 * * * cd <DHANRADAR-REPO-PATH> && bash scripts/backup-db.sh backup >> /var/log/dhanradar-backup.log 2>&1
```

## 3. Run or list manually

Run a backup now (from the repo root):

```bash
bash scripts/backup-db.sh backup
```

List the 20 most-recent backup objects in R2:

```bash
bash scripts/backup-db.sh list
```

## 4. Restore procedure

**This is a DESTRUCTIVE operation.**
Stop the application services before restoring.
Only a confirmed operator action should proceed.

### Step 1 — stop app services

```bash
docker compose -p dhanradar -f docker-compose.yml stop \
  dhanradar-fastapi \
  dhanradar-nextjs \
  dhanradar-celery-batch \
  dhanradar-celery-mood \
  dhanradar-celery-misc \
  dhanradar-celery-beat
```

Leave `dhanradar-postgres` running.

### Step 2 — download the dump from R2

Use the AWS CLI (configured with R2 credentials) or the R2 console.
Replace placeholders with real values from `docs/infra-notes.md`.

```bash
aws s3 cp \
  s3://<R2-BUCKET>/backups/postgres/YYYY/MM/DD/dhanradar-<UTC-timestamp>.dump \
  ./dhanradar-restore.dump \
  --endpoint-url <R2-ENDPOINT>
```

### Step 3 — copy the dump into the postgres container

```bash
docker cp ./dhanradar-restore.dump \
  $(docker compose -p dhanradar -f docker-compose.yml ps -q dhanradar-postgres):/tmp/dhanradar-restore.dump
```

### Step 4 — restore with pg\_restore

```bash
docker compose -p dhanradar -f docker-compose.yml exec -T dhanradar-postgres \
  pg_restore \
    -U dhanradar \
    -d dhanradar \
    --clean \
    --if-exists \
    /tmp/dhanradar-restore.dump
```

`--clean` drops and recreates objects before restoring — the operation is destructive.

### Step 5 — verify the restore

```bash
docker compose -p dhanradar -f docker-compose.yml exec -T dhanradar-postgres \
  psql -U dhanradar -d dhanradar \
  -c "SELECT COUNT(*) AS audit_rows FROM compliance.ai_recommendation_audit;"
```

Confirm the row count matches the expected volume.

### Step 6 — restart app services

```bash
docker compose -p dhanradar -f docker-compose.yml up -d
```

## 5. Retention and residency (DEPLOY GATE, OPEN)

**These are human and infra gates — no code change is required.**

- **R2 bucket India-residency** — the R2 bucket must be verified as India-resident
  before backups of user data are enabled in production.
  The `ai_recommendation_audit` dump contains `user_id` (DPDP personal data).
  The control is bucket residency; do NOT pseudonymize the archive (it is the
  7-year SEBI record-of-serving and must remain user-identifiable, per ADR-0022).
  This mirrors the B34 control for the daily audit archival job.

- **Retention lifecycle** — a retention policy (example: keep 30 daily dumps,
  delete older objects automatically) must be configured as an R2 bucket lifecycle
  policy. This is an infra gate, not a code gate.

- **Restore drill** — a tested restore against the live box must be performed and
  logged before backup is considered production-ready.

Until these three gates are cleared, the backup script may run in dev/staging
but must not be the sole recovery mechanism for production user data.

## 6. Pointer

Real values (bucket name, account ID, R2 endpoint, repo path, crontab placement)
are in `docs/infra-notes.md` on the KVM4 host.
That file is local-only and is never committed to the repository.
