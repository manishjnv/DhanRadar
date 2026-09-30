"""
DhanRadar — data deletion + retention policy (single source of truth).

Founder decisions 2026-09-30 (B79 follow-up). Every deletion/retention period in
the backend reads from here; the bash backup scripts and the R2 lifecycle rules
mirror these numbers and cite this file.

Legal basis (see docs/project-state/BLOCKERS.md B79): DPDP Act s.12(3) (erase on
request unless another law needs the data), DPDP Rules 2025 Rule 8(3) (logs kept
>= 1 year), PMLA (5 years after the relationship ends), Income-tax/GST (6 years),
SEBI broker rules / Companies Act (8 years).
"""

from __future__ import annotations

from datetime import timedelta

# ── Account deletion ──────────────────────────────────────────────────────────
# No erase before ERASURE_WAIT after the request (the user's cancel window, and
# protection against a stolen session deleting the account). ERASURE_DUE is our
# promise to the user: erased within this long of the request.
ERASURE_WAIT = timedelta(days=7)
ERASURE_DUE = timedelta(days=30)

# ── Records kept after erasure (random user ID only — no name/email/PAN) ─────
LEGAL_RECORD_RETENTION = timedelta(days=2922)  # 8 years (incl. 2 leap days)
LOG_RETENTION = timedelta(days=365)  # DPDP Rules 2025 Rule 8(3) minimum

# table -> how long a row is kept (measured from the row's created time), then
# deleted by the monthly retention job.
RETENTION_BY_TABLE: dict[str, timedelta] = {
    "consent.consent_audit_log": LEGAL_RECORD_RETENTION,
    "compliance.ai_recommendation_audit": LEGAL_RECORD_RETENTION,
    "audit.payment_events": LEGAL_RECORD_RETENTION,
    "audit.security_events": LOG_RETENTION,
    "audit.admin_actions": LOG_RETENTION,
}

# ── Backups (mirrored in scripts/backup.sh + the R2 lifecycle rules) ─────────
FULL_BACKUP_RETENTION_DAYS = 90
LEGAL_ARCHIVE_RETENTION_DAYS = 2922  # 8 years
