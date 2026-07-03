"""db_security — Row-Level Security (I5) single source of truth (B81).

Owner-scoping is enforced PHYSICALLY by Postgres RLS: every personal row is visible/writable only
when the request's `app.user_id` GUC matches the row's `user_id`. The runtime role `dhanradar_app`
is NOSUPERUSER NOBYPASSRLS (B80), so FORCE RLS genuinely binds it. Cross-user readers (admin
console, Celery aggregate jobs, webhooks) connect as the dedicated BYPASSRLS role `dhanradar_admin`.

ONE source: the migration, conftest, and the RLS tests all derive from the constants + `rls_statements`
here — so the policy set can never drift from what the tests assert (the B80 grant-gap lesson).

CLASSIFICATION (B81): every table with a `user_id` column is CONSCIOUSLY one of:
  - PERSONAL_TABLES   — owner-scoped; gets RLS.
  - AUDIT_EXEMPT      — append-only audit / admin-cross-user-read, NOT owner-read; the app already
                        cannot UPDATE/DELETE these (0052 REVOKE). NO user-facing "view my own X"
                        surface exists today; if one is added (e.g. a DPDP "view my consent" screen
                        over consent_audit_log), that table MOVES to PERSONAL_TABLES then.
None may be left unclassified — the drift test asserts (every user_id table) == PERSONAL ∪ AUDIT_EXEMPT.

ROLLOUT (founder 2026-06-27, staged): PR-1 ENFORCES RLS on RLS_ENFORCED (the 8 mf.* core tables) with
their readers fully wired; the remaining PERSONAL_TABLES (signal/notify/auth/compliance) are classified
+ infra-ready but enforcement is deferred to PR-2 (just move them into RLS_ENFORCED + wire their
readers). This bounds each PR's blast radius — a missed cross-user reader silently empties queries.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import event, text

#: Session GUC the owner policy reads. SET LOCAL (transaction-scoped) only — a plain SET would leak
#: across the pooled FastAPI engine to the next request.
APP_USER_GUC = "app.user_id"

#: ALL owner-scoped personal tables (schema-qualified). Drives the drift test (must equal reality).
PERSONAL_TABLES: tuple[str, ...] = (
    # mf (RLS-enforced in PR-1)
    "mf.mf_portfolios",
    "mf.mf_user_holdings",
    "mf.portfolio_transactions",
    "mf.mf_portfolio_snapshots",
    "mf.mf_cas_jobs",
    "mf.mf_user_fund_score_history",
    "mf.user_fund_scores",
    "mf.mf_sip_transactions",
    # M2.2 — daily portfolio valuation series (added 2026-06-30)
    "mf.mf_portfolio_daily_values",
    # §39.4 — per-upload statement checkpoints (added 2026-07-03)
    "mf.portfolio_statement_checkpoints",
    # signal / notify / auth / compliance (classified PERSONAL; RLS enforcement = PR-2)
    "signal.signal_rules",
    "signal.signal_dip_fund",
    "signal.signal_deployments",
    "signal.signal_journal",
    "signal.signal_notifications",
    # NB: signal.signal_history is NOT here — it is global per-date trust-engine history (unique on
    # `date`, NO user_id column), not owner-scoped personal data.
    "notify.notification_preferences",
    "notify.notification_log",
    "auth.subscriptions",
    "auth.user_activity_log",
    "compliance.ai_output_feedback",
)

#: Tables RLS is ENFORCED on. PR-1 enforced the 8 mf.* core tables; PR-2 added the remaining
#: signal/notify/auth/compliance personal tables — so RLS_ENFORCED now == PERSONAL_TABLES (full I5).
#: A future personal table is added to BOTH PERSONAL_TABLES and here in the same change (the
#: full-coverage test asserts the two sets are equal, so a personal table can't ship unenforced).
RLS_ENFORCED: tuple[str, ...] = (
    # mf (PR-1)
    "mf.mf_portfolios",
    "mf.mf_user_holdings",
    "mf.portfolio_transactions",
    "mf.mf_portfolio_snapshots",
    "mf.mf_cas_jobs",
    "mf.mf_user_fund_score_history",
    "mf.user_fund_scores",
    "mf.mf_sip_transactions",
    # M2.2 — daily portfolio valuation series (added 2026-06-30)
    "mf.mf_portfolio_daily_values",
    # §39.4 — per-upload statement checkpoints (added 2026-07-03)
    "mf.portfolio_statement_checkpoints",
    # signal / notify / auth / compliance (PR-2)
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
)

#: user_id-bearing tables that are NOT owner-read (append-only audit / admin-cross-user). Documented,
#: REVOKE-protected (0052). They are deliberately NOT RLS'd. Keep in sync with the drift test.
AUDIT_EXEMPT: tuple[str, ...] = (
    "audit.payment_events",
    "compliance.ai_recommendation_audit",
    "compliance.ai_low_confidence_log",
    "consent.consent_audit_log",
)

_POLICY = "owner_isolation"
# NULLIF: an empty-string GUC (or unset → NULL) yields NULL, so `user_id = NULL` is FALSE (deny-all,
# fail-SAFE) — and it never 500s on `''::uuid`.
_OWNER_EXPR = "(user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)"


def rls_statements(qualified_table: str) -> list[str]:
    """The exact DDL to put owner-scoped FORCE RLS on one `schema.table`. Idempotent (DROP POLICY IF
    EXISTS before CREATE). FORCE so even the table owner is bound. `qualified_table` is a trusted
    constant from RLS_ENFORCED (never user input)."""
    return [
        f"ALTER TABLE {qualified_table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {qualified_table} FORCE ROW LEVEL SECURITY",
        f"DROP POLICY IF EXISTS {_POLICY} ON {qualified_table}",
        f"CREATE POLICY {_POLICY} ON {qualified_table} "
        f"USING {_OWNER_EXPR} WITH CHECK {_OWNER_EXPR}",
    ]


def rls_downgrade_statements(qualified_table: str) -> list[str]:
    """Reverse of rls_statements (for the migration downgrade / CI reversibility)."""
    return [
        f"DROP POLICY IF EXISTS {_POLICY} ON {qualified_table}",
        f"ALTER TABLE {qualified_table} NO FORCE ROW LEVEL SECURITY",
        f"ALTER TABLE {qualified_table} DISABLE ROW LEVEL SECURITY",
    ]


async def set_rls_user(db: Any, user_id: str) -> None:
    """Scope the CURRENT transaction's RLS to `user_id` (SET LOCAL app.user_id, parameterized via
    set_config(...,is_local=true) — no injection, resets at commit/rollback so it never leaks across
    the pooled connection). Call after auth resolves the user (FastAPI: current_user_or_anonymous)
    and in per-user request writers before touching a personal table.

    NOTE: is_local=true means it RESETS at COMMIT/ROLLBACK. A request that commits mid-flow and then
    writes a personal table again must re-call this (else the policy denies all → 0 rows / a WITH
    CHECK rejection) — see auth.record_login and the cas_upload activity write, which re-call it after
    an intervening commit. A MULTI-commit per-user background writer (the CAS pipeline) uses
    `rls_user_session` instead, which re-applies the GUC automatically on every transaction begin."""
    await db.execute(
        text("SELECT set_config(:guc, :uid, true)"),
        {"guc": APP_USER_GUC, "uid": str(user_id)},
    )


@asynccontextmanager
async def rls_user_session(user_id: str) -> AsyncIterator[Any]:
    """A NullPool task session whose RLS owner GUC (`app.user_id`) is RE-APPLIED on EVERY transaction
    begin — the only robust way to keep one owner scope across a MULTI-commit per-user writer.

    Why an event, not a single set_rls_user: the CAS pipeline commits 3+ times (progress states) AND
    its helpers commit per fund (mf.history.append_score_history). A SET LOCAL is cleared by each
    commit, and on a NullPool engine the next transaction checks out a FRESH connection (so even a
    session-level SET is lost) — so the GUC must be re-set at the start of every transaction. The
    `after_begin` Session event fires on each begin (within the greenlet context, so the sync
    exec_driver_sql on the given connection is allowed for the async engine) and re-applies it. The
    value is SET LOCAL (transaction-scoped) and the connection is destroyed on release (NullPool), so
    it can never leak to another user.

    `user_id` is validated as a UUID up front, so a malformed owner raises here (never a silently
    unscoped bypass write). The re-apply runs on the sync `connection` the event hands us via bound
    params (SQLAlchemy translates the driver paramstyle) — no injection, no exec_driver_sql paramstyle
    mismatch."""
    from dhanradar.db import task_session

    uid = str(UUID(str(user_id)))  # canonical UUID or ValueError — fail rather than write unscoped

    async with task_session() as db:

        @event.listens_for(db.sync_session, "after_begin")
        def _apply_owner_guc(session: Any, transaction: Any, connection: Any) -> None:
            connection.execute(
                text("SELECT set_config(:guc, :uid, true)"),
                {"guc": APP_USER_GUC, "uid": uid},
            )

        yield db
