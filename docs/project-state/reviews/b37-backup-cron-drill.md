# Review Ledger — B37 backup cron + restore drill go-live

- **Change-id:** b37-backup-cron-drill · **Date:** 2026-06-12 · **Branch:** `feat/b37-backup-cron-drill`
- **Classification:** Tier-B (load-bearing: `scripts/` backup/restore path, host cron on KVM4,
  DPDP/SEBI-relevant data flows). Inline review in the landing session per the load-bearing
  exception — not deferred to the phase audit.
- **Scope:** `scripts/backup.sh` (backups/ prefix; `python -m alembic` MANIFEST fix),
  `scripts/restore.sh` (prefix resolution; TimescaleDB pre/post-restore wrappers; MANIFEST
  hardening), `scripts/restore-drill.sh` (new), `.env.example`, ops runbooks, RCA ×2,
  BLOCKERS B37/B34. Box actions: host cron 21:30 UTC + flock; aws CLI relocated to a
  dhanradar-scoped tools dir; fresh backup; two live restore drills.

## Deterministic gates

- `bash -n` ×3 scripts: PASS (pre- and post-hardening).
- Secrets scan on diff (full pattern set): CLEAN. TODO/FIXME: CLEAN.
- Infra-leak scan (real paths/bucket/host names in committed files): CLEAN — placeholders only.
- markdownlint on the 5 touched docs: 1 pre-existing MD004 hit (B56-era entry, on HEAD,
  advisory) — nothing introduced.
- CI: runs on the PR (the gate of record per house rule).

## Security review — Sonnet adversarial takeover (codex:rescue n/a on this account)

**Verdict: ACCEPT-WITH-CONDITIONS → conditions CLOSED in-session.** 18+ vectors probed;
clean on: argument/path injection, drill blast-radius (every docker op project-scoped to
`dhanradar-drill` + container-name assertion), credential temp-file pattern, timescale
wrapper failure modes. Findings and closure:

1. **BLOCKER — empty/stripped MANIFEST bypassed verification** (zero `file=` lines passed).
   Closed: `db_dump_verified` assertion after the parse loop in both restore scripts.
2. **BLOCKER — `sha256=absent` on a present file skipped its checksum.** Closed: absent +
   file-present now dies (tampering signal) in both restore scripts.
3. **BLOCKER — `aws s3 cp --recursive` plants key-derived paths (S3 keys may contain
   `/`/`..`) as root.** Closed with a STRONGER fix than proposed: the reviewer's post-download
   directory walk cannot see writes that landed outside the restore dir; instead both restore
   scripts now fetch the four artifacts explicitly by name (no `--recursive`), eliminating
   key-derived destination paths entirely.
4. MINOR — auto-detected latest stamp now constrained to `^[0-9]{14}$`. Closed.
5. NIT — cred-file trap registered before the secret is written (all three scripts). Closed.

**Accepted residual (documented):** a hostile `db.dump` executes SQL as the in-container
superuser at restore time — checksums prove integrity, not provenance; blast radius is the
postgres container/database only (no host bind-mounts beyond pgdata + ro init). A restore
from a compromised bucket is a disaster-declaration scenario, not a quiet pivot.

## Compliance review — independent Sonnet (Opus-tier reviewer n/a during Fable-only window)

**Verdict: ACCEPT-WITH-CONDITIONS → conditions CLOSED in-session.**

1. MAJOR — `backup.sh` header claimed "R2 (India)". Closed: now "target: India-resident;
   B34 — not yet verified".
2. MAJOR — runbook Purpose line + env-table row stated "India-resident" as present fact;
   `.env.example` implied the lifecycle rule exists. Closed: target-qualified wording,
   B34 pointers, "must be scoped … not yet set".
3. MINOR — risk-acceptance traceability: one sentence added to the runbook verified-state
   note recording the 2026-06-12 operator decision (B37 escalation: data-loss risk outweighs
   the unresolved residency question, pending B34 counsel review).
4. NIT — drill-log PASS criteria now include the pg_restore exit-zero gate. Closed.

Reviewer also confirmed: B37 "RESOLVED" is honest per register house style (core risk
eliminated; residuals documented inline); retention reasoning sound (no expiration rule =
indefinite retention ≥ the 7-yr floor; the rule is cost hygiene); both RCA entries factually
accurate; advisory-boundary sweep clean.

## Evidence (live, 2026-06-12)

- Host cron installed + verified: `30 21 * * * … flock -n /var/lock/dhanradar-backup.lock
  bash scripts/backup.sh …` (placeholders in docs; real paths in `docs/infra-notes.md`).
- Fresh backup: stamp `20260612171924`, db.dump 43,637,659 bytes → `backups/` prefix, SUCCESS.
- Restore drill #1 (pre-hardening): PASS — alembic `0018`, users 6, audit 41,
  NAV 5,954,403; 28 s. Drill #2 (hardened scripts, regression): PASS — 44 s.
- `get-bucket-location` = APAC hint; lifecycle Get/Put = AccessDenied on the Object-R/W
  token → lifecycle rule is an operator dashboard action (rule must be scoped to `backups/`).

## Sign-off

- Gates green · Security ACCEPT-W/C (closed) · Compliance ACCEPT-W/C (closed) →
  **merge-eligible**. Deploy-relevant box state already applied under the standing VPS
  authorization; repo↔box sync completes when this PR merges and the box pulls.
- Open follow-ups: B37-f1 (backup-failure alerting, LOW), R2 lifecycle rule (operator),
  B34 residency decision (operator/counsel), quarterly drill due 2026-09.
