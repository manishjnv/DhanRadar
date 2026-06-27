"""B81 PR-2 — extend schema-wide Row-Level Security (I5) to the remaining personal tables:
signal (5), notify (2), auth (2), compliance (1). Completes full I5 — every classified
PERSONAL_TABLE is now FORCE-RLS owner-scoped (RLS_ENFORCED == PERSONAL_TABLES).

PR-1 (0053) enforced RLS on the 8 mf.* tables AND created the dhanradar_admin BYPASSRLS role with
grants on every APP_SCHEMA (signal/notify/auth/compliance included). So this migration only adds the
FORCE-RLS + owner policy to the 10 remaining tables — no new role, no new grants. The cross-user
readers of these tables (signal alert Celery jobs, the notification drain, the Razorpay webhook) were
moved onto the admin engine in the same PR; per-user writers (record_login, cas_upload activity log,
the CAS pipeline) set the app.user_id GUC before writing.

The owner-policy DDL is db_security.rls_statements (single source — conftest + the RLS tests apply the
SAME), so the policy shape can't drift; the table list is inlined as literals (frozen + so the B83
drift text-assert can verify 0053 ∪ 0054 == db_security.RLS_ENFORCED).

Revision ID: 0054
Revises: 0053
Create Date: 2026-06-27
"""

from __future__ import annotations

from alembic import op
from dhanradar.db_security import rls_downgrade_statements, rls_statements

revision: str = "0054"
down_revision: str | None = "0053"
branch_labels = None
depends_on = None

# Inlined as literals (frozen + greppable by the B83 drift text-assert). MUST be the
# RLS_ENFORCED tables NOT already enforced by 0053; together 0053 ∪ 0054 == db_security.RLS_ENFORCED.
_RLS_TABLES = [
    "signal.signal_rules",
    "signal.signal_dip_fund",
    "signal.signal_deployments",
    "signal.signal_journal",
    "signal.signal_notifications",
    "notify.notification_preferences",
    "notify.notification_log",
    "auth.subscriptions",
    "auth.user_activity_log",
    "compliance.ai_output_feedback",
]


def upgrade() -> None:
    # FORCE RLS + owner policy on each remaining personal table (DDL from db_security,
    # to_regclass-guarded so a not-yet-created table is skipped, not a hard error).
    for table in _RLS_TABLES:
        body = ";\n                ".join(rls_statements(table)) + ";"
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('{table}') IS NOT NULL THEN
                {body}
                END IF;
            END $$;
            """
        )


def downgrade() -> None:
    for table in _RLS_TABLES:
        body = ";\n                ".join(rls_downgrade_statements(table)) + ";"
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('{table}') IS NOT NULL THEN
                {body}
                END IF;
            END $$;
            """
        )
