"""
DhanRadar — DPDP account-lifecycle: deletion request + hard user erasure (B79).

Two operations, both admin-triggered (no automatic schedule — the grace period
between "deletion requested" and "hard erase" is a founder decision, tracked in
BLOCKERS.md B79):

  * ``request_user_deletion`` — sets ``auth.users.deletion_requested_at`` and
    (B4 / B33(b) residual) tears down the user's EXISTING sessions: revokes
    every live refresh jti and flushes the ``auth:tier:{uid}`` cache, so a
    session issued before the request stops working immediately rather than
    riding out its TTL.
  * ``hard_erase_user`` — the actual DPDP right-to-erasure. Refuses unless
    ``deletion_requested_at`` is already set (never erases an active account).

FK map (Step 1 investigation, 2026-09-30 — see the session report for the full
table): every personal-data table that carries a hard FK to ``auth.users.id``
is ``ondelete="CASCADE"`` (mf.*, notify.*, auth.subscriptions,
auth.user_activity_log) — deleting the ``auth.users`` row removes them
automatically. ``mf.portfolio_transactions`` is one of those CASCADE tables
but also carries the I12 append-only trigger (migration 0050), so
``allow_ledger_purge`` MUST be called first in the same transaction (mirrors
``mf.router.delete_portfolio``) or the cascade is blocked and erasure fails.

A SMALL number of personal-data tables carry NO FK at all (by design — they
predate the FK, or were deliberately left loose) and would be ORPHANED by a
plain ``DELETE FROM auth.users``: ``signal.signal_rules``,
``signal.signal_dip_fund``, ``signal.signal_deployments``,
``signal.signal_journal``, ``signal.signal_notifications``, and
``compliance.ai_output_feedback``. Those are deleted explicitly, before the
``auth.users`` delete.

LEGAL-RETENTION tables (SEBI 7-yr / DPDP consent-of-record) are untouched by
design — they carry NO FK to ``auth.users`` on purpose, so cascade can never
reach them: ``consent.consent_audit_log``, ``compliance.ai_recommendation_audit``,
``audit.admin_actions``, ``audit.payment_events``, ``audit.security_events``.
They are not referenced anywhere in this module — that omission IS the safety
property (nothing here can delete them). ``audit.security_events`` already
stores a hashed ``user_ref`` instead of a raw id; the others still hold a raw
``user_id`` and are retained un-pseudonymised — pseudonymising them post-erasure
is a follow-up, not built here (see the session report's open founder
decisions).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.auth.service import REFRESH_KEY_PREFIX, TIER_CACHE_PREFIX
from dhanradar.core.logging import get_logger
from dhanradar.mf.ledger import allow_ledger_purge
from dhanradar.models.auth import Subscription, User, UserActivityLog
from dhanradar.models.compliance import AiOutputFeedback
from dhanradar.models.mf import (
    MfCasJob,
    MfPortfolio,
    MfPortfolioDailyValue,
    MfPortfolioSnapshot,
    MfPortfolioStatementCheckpoint,
    MfPortfolioTransaction,
    MfSipTransaction,
    MfUserFundScoreHistory,
    MfUserHolding,
    MfWatchlistAlert,
    MfWatchlistItem,
    UserFundScore,
)
from dhanradar.models.notifications import NotificationLog, NotificationPreference
from dhanradar.redis_client import get_redis
from dhanradar.signal.models import (
    SignalDeployment,
    SignalDipFund,
    SignalJournal,
    SignalNotification,
    SignalRules,
)

_slog = get_logger(__name__)


class UserNotFoundError(Exception):
    """No ``auth.users`` row for the given id."""


class DeletionNotRequestedError(Exception):
    """Erasure refused — ``deletion_requested_at`` is not set (active account)."""


# FK-CASCADE tables (auth.users.id ondelete=CASCADE) — deleting the user row
# removes these automatically. Pre-counted (not explicitly deleted) so the
# report has real numbers. mf.mf_sip_transactions has no direct FK to
# auth.users but cascades transitively via portfolio_id -> mf.mf_portfolios.id
# (also CASCADE), so it belongs in this list, not the explicit-delete one.
_CASCADE_TABLES: list[tuple[str, type, Any]] = [
    ("mf.mf_watchlist_items", MfWatchlistItem, MfWatchlistItem.user_id),
    ("mf.mf_watchlist_alerts", MfWatchlistAlert, MfWatchlistAlert.user_id),
    ("mf.mf_portfolios", MfPortfolio, MfPortfolio.user_id),
    ("mf.mf_user_holdings", MfUserHolding, MfUserHolding.user_id),
    ("mf.portfolio_transactions", MfPortfolioTransaction, MfPortfolioTransaction.user_id),
    ("mf.mf_portfolio_snapshots", MfPortfolioSnapshot, MfPortfolioSnapshot.user_id),
    ("mf.mf_cas_jobs", MfCasJob, MfCasJob.user_id),
    (
        "mf.portfolio_statement_checkpoints",
        MfPortfolioStatementCheckpoint,
        MfPortfolioStatementCheckpoint.user_id,
    ),
    (
        "mf.mf_user_fund_score_history",
        MfUserFundScoreHistory,
        MfUserFundScoreHistory.user_id,
    ),
    ("mf.user_fund_scores", UserFundScore, UserFundScore.user_id),
    ("mf.mf_sip_transactions", MfSipTransaction, MfSipTransaction.user_id),
    ("mf.mf_portfolio_daily_values", MfPortfolioDailyValue, MfPortfolioDailyValue.user_id),
    (
        "notify.notification_preferences",
        NotificationPreference,
        NotificationPreference.user_id,
    ),
    ("notify.notification_log", NotificationLog, NotificationLog.user_id),
    ("auth.subscriptions", Subscription, Subscription.user_id),
    ("auth.user_activity_log", UserActivityLog, UserActivityLog.user_id),
]

# NO-FK tables — orphan risk. Deleted explicitly, before DELETE FROM auth.users.
_EXPLICIT_DELETE_TABLES: list[tuple[str, type, Any]] = [
    ("signal.signal_rules", SignalRules, SignalRules.user_id),
    ("signal.signal_dip_fund", SignalDipFund, SignalDipFund.user_id),
    ("signal.signal_deployments", SignalDeployment, SignalDeployment.user_id),
    ("signal.signal_journal", SignalJournal, SignalJournal.user_id),
    ("signal.signal_notifications", SignalNotification, SignalNotification.user_id),
    ("compliance.ai_output_feedback", AiOutputFeedback, AiOutputFeedback.user_id),
]


async def _revoke_all_refresh_jtis(user_id: str) -> int:
    """Best-effort revoke of every live refresh jti belonging to *user_id*.

    ``auth:refresh:{jti} -> user_id`` has no reverse (per-user) index (documented
    limitation, admin/users_router.py reset_user_access), so this SCANs the
    refresh-jti keyspace and deletes the ones whose value matches.
    ponytail: O(active refresh sessions) SCAN, fine at pre-launch scale; add a
    per-user jti SET index if that keyspace ever gets large.
    """
    redis = get_redis()
    revoked = 0
    async for key in redis.scan_iter(match=f"{REFRESH_KEY_PREFIX}*"):
        try:
            owner = await redis.get(key)
        except Exception:  # pragma: no cover - defensive, matches reset_user_access style
            continue
        if owner == user_id:
            await redis.delete(key)
            revoked += 1
    return revoked


async def request_user_deletion(db: AsyncSession, user_id: UUID) -> None:
    """Mark *user_id* for deletion and immediately tear down their sessions.

    Idempotent: re-requesting an already-pending deletion just re-stamps the
    timestamp and re-runs the session teardown (harmless — there is nothing
    left to revoke on a second call).

    Does NOT erase any data — see ``hard_erase_user`` for the actual purge.
    """
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise UserNotFoundError()

    user.deletion_requested_at = datetime.now(UTC)
    await db.commit()

    uid_str = str(user_id)
    revoked = await _revoke_all_refresh_jtis(uid_str)
    redis = get_redis()
    await redis.delete(f"{TIER_CACHE_PREFIX}{uid_str}")
    _slog.info("erasure.deletion_requested", refresh_jtis_revoked=revoked)


async def hard_erase_user(db: AsyncSession, user_id: UUID) -> dict[str, int]:
    """DPDP hard erasure (B79). Refuses unless ``deletion_requested_at`` is set.

    One transaction: arm the ledger-purge GUC FIRST (mirrors
    ``mf.router.delete_portfolio``), explicitly delete the NO-FK personal
    tables, then ``DELETE FROM auth.users`` — the CASCADE FKs take care of
    every other personal-data table (see module docstring for the full map).
    Legal-retention tables are never touched (no FK reaches them, and this
    module never references them).

    Returns per-table row counts (no PII — just table label -> int). Redis
    per-user keys are cleared AFTER commit (best-effort, never blocks the
    already-committed erasure).
    """
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise UserNotFoundError()
    if user.deletion_requested_at is None:
        raise DeletionNotRequestedError()

    counts: dict[str, int] = {}
    for label, model, col in _CASCADE_TABLES + _EXPLICIT_DELETE_TABLES:
        counts[label] = int(
            await db.scalar(select(func.count()).select_from(model).where(col == user_id)) or 0
        )

    # Sanctioned bypass of the I12 append-only trigger for this ONE transaction
    # (SET LOCAL — auto-reverts at commit; see mf/ledger.py).
    await allow_ledger_purge(db)

    for _label, model, col in _EXPLICIT_DELETE_TABLES:
        await db.execute(delete(model).where(col == user_id))

    result = await db.execute(delete(User).where(User.id == user_id))
    counts["auth.users"] = result.rowcount or 0  # type: ignore[attr-defined]

    await db.commit()

    uid_str = str(user_id)
    redis = get_redis()
    try:
        await redis.delete(f"{TIER_CACHE_PREFIX}{uid_str}")
        await _revoke_all_refresh_jtis(uid_str)
    except Exception:  # pragma: no cover - best-effort, erasure already committed
        _slog.warning("erasure.redis_cleanup_failed")

    _slog.info("erasure.hard_erased", tables=len(counts))
    return counts
