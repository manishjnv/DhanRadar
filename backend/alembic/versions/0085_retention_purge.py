"""Monthly retention purge (DPDP/SEBI) for the 5 legal/audit tables in data_policy.py.

Adds `compliance.retention_policy()` (single source of the 5 intervals, matching
dhanradar.compliance.data_policy.RETENTION_BY_TABLE) and `compliance.retention_purge()`
(SECURITY DEFINER, no args — the caller cannot choose a cutoff) that deletes rows older
than their table's period and returns a per-table jsonb count.

Why SECURITY DEFINER instead of a trigger-escape-hatch (I12's `mf.allow_ledger_purge`
pattern): 4 of the 5 tables (audit.* + compliance.ai_recommendation_audit) already have
UPDATE/DELETE hard-REVOKEd from both runtime roles at the grant level (0052/0053) — no
trigger exists or is needed, so a function owned by the migration/owner role naturally
bypasses the revoke while the roles themselves stay locked out. `consent.consent_audit_log`
had NO such revoke (a pre-existing gap — it only inherited the schema-wide `consent` grant
from 0052, which includes UPDATE/DELETE); this migration closes that gap by revoking
UPDATE/DELETE on it too, from both dhanradar_app and dhanradar_admin.

EXECUTE on both functions is granted only to dhanradar_admin — the BYPASSRLS role Celery's
cross-user aggregate jobs connect as (db.py `admin_task_session`); the retention purge scans
across all users' rows, so it is a cross-user job like rescore/snapshot-refresh, never a
per-user task on dhanradar_app.

# ponytail: partitioned tables (ai_recommendation_audit/payment_events/security_events/
# admin_actions) are purged with a plain DELETE on the parent, not a partition-DROP. Correct
# and simple — Postgres routes a DELETE through every partition. Add partition-DROP only if
# partition count/row volume makes the DELETE scan too slow in prod.

Downgrade drops both functions and restores consent.consent_audit_log's pre-migration grants
(re-GRANT UPDATE/DELETE to dhanradar_app + dhanradar_admin, matching the schema-wide grant it
had before). No triggers were added, so there is nothing else to restore.

Revision ID: 0085
Revises: 0084
Create Date: 2026-09-30
"""

from __future__ import annotations

from alembic import op

revision: str = "0085"
down_revision: str | None = "0084"
branch_labels = None
depends_on = None

# Single source inside the DB — compliance.retention_purge() reads these via
# compliance.retention_policy() instead of hardcoding the interval twice.
# MUST match dhanradar.compliance.data_policy.RETENTION_BY_TABLE.
_RETENTION_POLICY_SQL = """
CREATE OR REPLACE FUNCTION compliance.retention_policy()
RETURNS TABLE(table_name text, retention_interval interval)
LANGUAGE sql
STABLE
SET search_path = pg_catalog, pg_temp
AS $$
    VALUES
        ('consent.consent_audit_log'::text, interval '2922 days'),
        ('compliance.ai_recommendation_audit'::text, interval '2922 days'),
        ('audit.payment_events'::text, interval '2922 days'),
        ('audit.security_events'::text, interval '365 days'),
        ('audit.admin_actions'::text, interval '365 days')
$$;
"""

_RETENTION_PURGE_SQL = """
CREATE OR REPLACE FUNCTION compliance.retention_purge()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    n_consent  bigint;
    n_ai_audit bigint;
    n_payment  bigint;
    n_security bigint;
    n_admin    bigint;
BEGIN
    DELETE FROM consent.consent_audit_log
     WHERE created_at < now() - (
        SELECT retention_interval FROM compliance.retention_policy()
         WHERE table_name = 'consent.consent_audit_log');
    GET DIAGNOSTICS n_consent = ROW_COUNT;

    DELETE FROM compliance.ai_recommendation_audit
     WHERE served_at < now() - (
        SELECT retention_interval FROM compliance.retention_policy()
         WHERE table_name = 'compliance.ai_recommendation_audit');
    GET DIAGNOSTICS n_ai_audit = ROW_COUNT;

    DELETE FROM audit.payment_events
     WHERE ts < now() - (
        SELECT retention_interval FROM compliance.retention_policy()
         WHERE table_name = 'audit.payment_events');
    GET DIAGNOSTICS n_payment = ROW_COUNT;

    DELETE FROM audit.security_events
     WHERE ts < now() - (
        SELECT retention_interval FROM compliance.retention_policy()
         WHERE table_name = 'audit.security_events');
    GET DIAGNOSTICS n_security = ROW_COUNT;

    DELETE FROM audit.admin_actions
     WHERE ts < now() - (
        SELECT retention_interval FROM compliance.retention_policy()
         WHERE table_name = 'audit.admin_actions');
    GET DIAGNOSTICS n_admin = ROW_COUNT;

    RETURN jsonb_build_object(
        'consent.consent_audit_log', n_consent,
        'compliance.ai_recommendation_audit', n_ai_audit,
        'audit.payment_events', n_payment,
        'audit.security_events', n_security,
        'audit.admin_actions', n_admin
    );
END;
$$;
"""


def upgrade() -> None:
    # Close the pre-existing gap: consent.consent_audit_log inherited UPDATE/DELETE from the
    # schema-wide `consent` grant (0052) — no per-table revoke existed for it, unlike the audit
    # schema + ai_recommendation_audit. Mirror the 0052/0053 pattern exactly.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('consent.consent_audit_log') IS NOT NULL THEN
                EXECUTE 'REVOKE UPDATE, DELETE ON TABLE consent.consent_audit_log FROM dhanradar_app';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('consent.consent_audit_log') IS NOT NULL
               AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dhanradar_admin') THEN
                EXECUTE 'REVOKE UPDATE, DELETE ON TABLE consent.consent_audit_log FROM dhanradar_admin';
            END IF;
        END $$;
        """
    )

    op.execute(_RETENTION_POLICY_SQL)
    op.execute(_RETENTION_PURGE_SQL)

    # 0052/0053 set `ALTER DEFAULT PRIVILEGES IN SCHEMA compliance GRANT EXECUTE ON FUNCTIONS`
    # to BOTH dhanradar_app and dhanradar_admin — so the CREATE FUNCTION above just auto-granted
    # EXECUTE to dhanradar_app too (default privileges apply to every new object silently). REVOKE
    # ALL FROM PUBLIC does not touch that role-specific grant; explicitly REVOKE it from
    # dhanradar_app so only dhanradar_admin (the Celery role for this cross-user job) keeps EXECUTE
    # (which the same default-privilege mechanism already grants it — the explicit GRANT below is
    # belt-and-suspenders documentation of intent, not load-bearing).
    op.execute("REVOKE ALL ON FUNCTION compliance.retention_policy() FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION compliance.retention_purge() FROM PUBLIC")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dhanradar_app') THEN
                REVOKE EXECUTE ON FUNCTION compliance.retention_policy() FROM dhanradar_app;
                REVOKE EXECUTE ON FUNCTION compliance.retention_purge() FROM dhanradar_app;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dhanradar_admin') THEN
                GRANT EXECUTE ON FUNCTION compliance.retention_policy() TO dhanradar_admin;
                GRANT EXECUTE ON FUNCTION compliance.retention_purge() TO dhanradar_admin;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS compliance.retention_purge()")
    op.execute("DROP FUNCTION IF EXISTS compliance.retention_policy()")

    # Restore consent.consent_audit_log to its pre-migration state (implicit UPDATE/DELETE via
    # the schema-wide consent grant).
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('consent.consent_audit_log') IS NOT NULL THEN
                EXECUTE 'GRANT UPDATE, DELETE ON TABLE consent.consent_audit_log TO dhanradar_app';
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dhanradar_admin') THEN
                    EXECUTE 'GRANT UPDATE, DELETE ON TABLE consent.consent_audit_log TO dhanradar_admin';
                END IF;
            END IF;
        END $$;
        """
    )
