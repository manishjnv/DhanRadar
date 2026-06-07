# Review — B37 DB backup automation

## Gate ledger

**Tier:** infra/ops + data-protection (writes the DB incl. the 7-yr `ai_recommendation_audit`
trail to R2) · **Class:** major (closes a CRITICAL data-loss deploy gate) · **Branch:**
`feat/b37-db-backup` (off `main`) · **Date:** 2026-06-07.

**Artifacts:** `scripts/backup-db.sh` (new), `backend/dhanradar/ops/{__init__,r2_put}.py` (new),
`docs/ops/backup-and-restore.md` (new), `backend/tests/unit/test_backup.py` (new, 5),
`docs/project-state/BLOCKERS.md` (B37 → ADDRESSED).

| Gate | Required | Verdict | Reviewer/tier |
|---|---|---|---|
| Deterministic (bash -n + pytest + markdownlint + secret scan) | always | PASS (syntax OK; 5 unit; MD clean; no leak) | machine |
| Architect | always | self-note (dependency-free; reuses storage.put_object; scoped `-p dhanradar`; no Dockerfile/compose change) | orchestrator (Opus) |
| Compliance | data-protection | ACCEPT (backup carries `user_id`/audit → R2 India-residency is a documented deploy gate, mirrors B34; password stays in-container) | orchestrator (Opus) |

**Review level (proportionate):** Builder + Architect + Compliance(Opus). No separate
`codex:rescue`/Sonnet adversarial pass — B37 is a **read-only** DB op (`pg_dump`) with a far smaller
blast radius than the B36 deploy orchestrator: scoped `-p dhanradar`, no host touch, timestamped
keys never overwrite good backups. The one material risk was caught in Opus review (below). Scaled
rigor per the playbook's "scale rigor to change magnitude."

## Design

`pg_dump -Fc` runs inside the live `dhanradar-postgres` container (pg16 ships `pg_dump`; `-Fc`
streams). Its stdout pipes to a **one-off `run --rm` container** from the fastapi image running
`python -m dhanradar.ops.r2_put <key>`, which uploads to R2 via the existing `storage.put_object`.
Dependency-free (no Dockerfile/compose change), credentials stay inside the containers, no temp file
on the host. HOST cron (21:30 UTC = 03:00 IST) decouples backup reliability from app-container
health. Two failure rails: `set -o pipefail` propagates a `pg_dump` failure through the pipe, and
`r2_put`'s empty-dump guard (exit 3) refuses to upload 0 bytes.

## Opus review finding (fixed in-session)

- **OOM-the-live-API risk (fixed):** the builder ran the uploader via `exec -T dhanradar-fastapi`
  — i.e. a python process reading the whole dump into memory **inside the serving API container**
  (512M cgroup shared with uvicorn); a large dump could trip the OOM-killer and kill the live API
  during a backup. Changed to `run --rm -T dhanradar-fastapi` (isolated cgroup) so backup memory can
  never OOM the serving process.

Residual (documented, not blocking): a `pg_dump` that fails mid-stream can upload a *partial* `-Fc`
object (non-empty, so the empty-guard misses it), but the pipe still aborts (pipefail) and a
truncated custom-format dump fails `pg_restore`'s trailer validation — detectable at restore, and
each backup is a fresh timestamped key so good history is never overwritten. A post-upload verify
step is a future enhancement.

## Final status

**ACCEPT.** Merge-eligible. **REMAINING (deploy gates, human/infra):** R2 bucket **India-residency**
verification before enabling in prod (DPDP, like B34); the R2 retention lifecycle policy; and a
**tested restore drill** on the live box. The backup is UNTESTED against the live stack until then.
