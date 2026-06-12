# DhanRadar — Restore Drill Log (B37)

## Purpose

Quarterly mandatory drill per B37. An untested backup is not a backup. Every quarter,
a full restore must be performed into the isolated `dhanradar-drill` Compose project and
the outcome logged here before the next drill is due.

## How to run

From the repo root:

```bash
bash scripts/restore-drill.sh [<backup-stamp>]
```

Omit the stamp to use the most recent backup in R2. The script automates the full
isolated-project restore, verifies alembic revision and row counts, measures timings,
and tears down the drill stack on success. See `scripts/restore-drill.sh` and
`docs/ops/backup-restore-runbook.md` (Restore drill section) for full details.

## What PASS means

All of the following hold:

- Backup artifacts fetched from R2 and MANIFEST sha256 verified.
- `timescaledb_pre_restore` / `pg_restore` / `timescaledb_post_restore` sequence completed
  without `--exit-on-error` failures.
- `pg_restore` exited zero (enforced by the script — a non-zero exit leaves the drill
  stack up for diagnosis and the result is FAIL).
- Restored alembic revision matches the MANIFEST revision (or, for pre-fix MANIFESTs
  saying `unavailable`, is present and well-formed).
- `auth.users` and `ai_recommendation_audit` counts return numerically (tables present
  and queryable — compare against expected values by hand for the log entry).
- NAV row count is greater than zero (proves hypertable data restored correctly).
- Drill stack torn down cleanly (`docker compose down -v`).

## Drill records

```
drill_date_utc:   2026-06-12
backup_stamp:     20260612171924
backup_alembic:   unavailable (pre-fix MANIFEST; restored rev verified instead)
restored_alembic: 0018
auth_users:       6
audit_rows:       41
nav_rows:         5954403
fetch_seconds:    9
restore_seconds:  18
verify_seconds:   1
total_seconds:    28
result:           PASS
operator:         Claude (B37 session); first-ever validated restore
```

```
drill_date_utc:   2026-06-12
backup_stamp:     20260612171924 (same backup; regression re-run)
restored_alembic: 0018
auth_users:       6
audit_rows:       41
nav_rows:         5954403
fetch_seconds:    26
restore_seconds:  17
verify_seconds:   1
total_seconds:    44
result:           PASS
operator:         Claude (B37 session); re-run after Tier-B security hardening
                  (per-object fetches replace cp --recursive — adds ~17 s fetch overhead)
```

Next drill due: **2026-09**.
