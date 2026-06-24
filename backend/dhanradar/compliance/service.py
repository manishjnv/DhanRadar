"""
DhanRadar — Compliance Audit service (architecture Global §4, B26).

Responsibilities:
  * `record_served_label(...)` — fire-and-forget write of one served label to the
    7-yr `ai_recommendation_audit` trail. Opens its OWN DB session and swallows all
    errors (logged) so an audit failure NEVER breaks or corrupts the serving path;
    the table's DEFAULT partition + denormalized `disclaimer_version` mean the row is
    not lost to a missing partition or a referential hiccup.
  * `get_active_disclaimer(db, type)` — read the in-force disclaimer (Redis-cached 1h).
  * `create_disclaimer(db, ...)` — insert a new disclaimer version (INACTIVE).
  * `activate_disclaimer(db, ...)` — promote one version to active (single-active-per-type).
  * `_snapshot_from_rows(rows)` — pure helper: group audit rows into date→key→label dict.
  * `label_churn_review(db, ...)` — churn gate over the two most-recent audit days.
  * `log_low_confidence(...)` — fire-and-forget low-confidence event log (no writer yet).
  * `record_engine_changelog(db, ...)` — insert one scoring methodology changelog row.

`recommendation_type='buy_sell'` is rejected at the DB (CHECK) AND defensively here.
"""

from __future__ import annotations

import hashlib
import html as _html
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Disclaimer creation / activation helpers
# ---------------------------------------------------------------------------

_KNOWN_DISCLAIMER_TYPES = frozenset({"ai_recommendation"})


class DisclaimerConflictError(Exception):
    """Raised when a disclaimer with the requested version already exists."""


class ActivationConflictError(Exception):
    """Raised when a concurrent activation would leave two disclaimers of the same
    type active at once (the DB partial-unique index rejects the losing commit)."""


# Max disclaimer body length — bounds an admin-only DoS against DB/R2/Redis on
# activation (a disclaimer is a short legal paragraph, never a large document).
_MAX_DISCLAIMER_CONTENT = 65536

_DISCLAIMER_CACHE_PREFIX = "disclaimer:active:"
_DISCLAIMER_TTL = 3600

# POSITIVE allowlist of auditable recommendation types — only educational labels
# may be recorded as served (non-neg #1). Anything else (incl. any advisory verb)
# is refused before the DB. Mirrors the DB CHECK `ck_audit_recommendation_type`.
_ALLOWED_TYPES = frozenset({"educational_label", "mood_regime"})


async def bump_audit_metric(name: str, amount: int = 1) -> None:
    """Best-effort daily Redis counter for compliance-audit observability (B34).
    Ops/alerting reads ``metrics:compliance:{name}:{YYYYMMDD}``. NEVER raises — an
    observability failure must not touch the serve/audit path."""
    try:
        from dhanradar.redis_client import get_redis

        redis = get_redis()
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        key = f"metrics:compliance:{name}:{day}"
        await redis.incrby(key, amount)
        await redis.expire(key, 35 * 86400)  # self-clean; alerting reads are recent
    except Exception:  # noqa: BLE001 — observability is best-effort
        logger.debug("compliance: metric bump failed for %s", name, exc_info=True)


def active_disclaimer_version() -> str:
    """The in-force disclaimer version (compliance is the §4 authority for it).
    A sync constant for fire-and-forget call sites; the DB-backed
    `get_active_disclaimer` is the authoritative async lookup. Callers that know
    the version served at generation should pin THAT instead of calling this."""
    from dhanradar.scoring.engine.schemas import DISCLAIMER_VERSION

    return DISCLAIMER_VERSION


def content_hash(payload: dict) -> str:
    """SHA-256 over a canonical JSON of the served payload (integrity anchor)."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def record_served_label(
    *,
    surface: str,
    label: Optional[str],
    model: Optional[str],
    disclaimer_version: str,
    recommendation_type: str = "educational_label",
    user_id: Optional[str] = None,
    identifier: Optional[str] = None,
    confidence_band: Optional[str] = None,
    prompt_version: Optional[str] = None,
    session_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> bool:
    """Persist one audit row. Returns True iff written. NEVER raises — a failure is
    logged and swallowed (the caller's serve path must not break on audit).

    `served_at` is ALWAYS the server's current UTC time (never caller-supplied), so
    an audit row cannot be backdated to misattribute a different in-force disclaimer."""
    if recommendation_type not in _ALLOWED_TYPES:
        # Defense-in-depth above the DB CHECK — never even attempt to audit a
        # non-educational (e.g. advisory) type (non-neg #1).
        logger.error("compliance: refused to audit non-allowlisted type=%r", recommendation_type)
        return False

    try:
        from dhanradar.db import TaskSessionLocal
        from dhanradar.models.compliance import AiRecommendationAudit

        payload = {
            "surface": surface, "label": label, "model": model,
            "disclaimer_version": disclaimer_version, "identifier": identifier,
            "recommendation_type": recommendation_type,
        }
        async with TaskSessionLocal() as db:
            db.add(
                AiRecommendationAudit(
                    served_at=datetime.now(timezone.utc),  # server-set, never caller-supplied
                    user_id=UUID(user_id) if user_id and user_id != "anonymous" else None,
                    recommendation_type=recommendation_type,
                    label=label,
                    content_hash=content_hash(payload),
                    model=model,
                    prompt_version=prompt_version,
                    confidence_band=confidence_band,
                    disclaimer_version=disclaimer_version,
                    surface=surface,
                    session_id=session_id,
                    request_id=request_id,
                )
            )
            await db.commit()
        return True
    except Exception:  # noqa: BLE001 — fire-and-forget: audit must not break the serve path
        logger.exception("compliance: audit write failed surface=%s label=%s", surface, label)
        await bump_audit_metric("audit_write_failures")
        return False


async def get_active_disclaimer(db: Any, disclaimer_type: str) -> Optional[dict]:
    """Return the active disclaimer for a type (Redis-cached 1h; Postgres fallback)."""
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    cache_key = f"{_DISCLAIMER_CACHE_PREFIX}{disclaimer_type}"
    try:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:  # noqa: BLE001 — cache is best-effort
        pass

    from sqlalchemy import select

    from dhanradar.models.compliance import Disclaimer

    row = await db.scalar(
        select(Disclaimer).where(
            Disclaimer.type == disclaimer_type, Disclaimer.active.is_(True)
        ).order_by(Disclaimer.effective_from.desc())
    )
    if row is None:
        return None
    result = {"type": row.type, "version": row.version, "content": row.content}
    try:
        await redis.set(cache_key, json.dumps(result), ex=_DISCLAIMER_TTL)
    except Exception:  # noqa: BLE001
        pass
    return result


async def create_disclaimer(
    db: Any,
    *,
    version: str,
    content: str,
    type: str = "ai_recommendation",
    created_by: str,
) -> dict:
    """Insert a new disclaimer version as INACTIVE.

    Activation is a separate, deliberate step (``activate_disclaimer``) so that
    an operator can review the content before it goes live.

    Raises:
        ValueError: if version/type/content validation fails.
        DisclaimerConflictError: if a disclaimer with that version already exists.
    """
    from sqlalchemy import select

    from dhanradar.models.compliance import Disclaimer

    version = version.strip()
    if not version or len(version) > 128:
        raise ValueError(
            f"version must be a non-empty string of at most 128 characters, got {version!r}"
        )
    if type not in _KNOWN_DISCLAIMER_TYPES:
        raise ValueError(
            f"unknown disclaimer type {type!r}; valid types: {sorted(_KNOWN_DISCLAIMER_TYPES)}"
        )
    if not content or not content.strip():
        raise ValueError("content must be non-empty")
    if len(content) > _MAX_DISCLAIMER_CONTENT:
        raise ValueError(
            f"content exceeds the {_MAX_DISCLAIMER_CONTENT}-char limit (len={len(content)})"
        )

    existing = await db.scalar(select(Disclaimer).where(Disclaimer.version == version))
    if existing is not None:
        raise DisclaimerConflictError(version)

    # Created INACTIVE — activation is a separate, deliberate step.
    row = Disclaimer(version=version, type=type, content=content, active=False)
    db.add(row)
    await db.commit()
    return {"version": version, "type": type, "active": False, "created_by": created_by}


async def activate_disclaimer(db: Any, *, version: str, activated_by: str) -> dict:
    """Promote one disclaimer version to active; deactivate all others of the same type.

    Single-active-per-type invariant is enforced in ONE transaction. After commit,
    attempts a best-effort R2 HTML snapshot and Redis cache flush (both silently
    degrade on failure so the committed activation is never rolled back).

    Raises:
        KeyError: if no disclaimer with that version exists.
    """
    from sqlalchemy import select, update
    from sqlalchemy.exc import IntegrityError

    from dhanradar import storage
    from dhanradar.models.compliance import Disclaimer
    from dhanradar.redis_client import get_redis

    row = await db.scalar(select(Disclaimer).where(Disclaimer.version == version))
    if row is None:
        raise KeyError(version)

    now = datetime.now(timezone.utc)

    # Deactivate all currently-active disclaimers of the same type in one UPDATE,
    # then activate the target row — single transaction, single commit. The
    # `uq_disclaimer_active_per_type` partial-unique index enforces the
    # single-active-per-type invariant atomically: a concurrent activation of a
    # different version races to commit, and the loser's commit is rejected
    # (IntegrityError) rather than silently leaving two versions active.
    await db.execute(
        update(Disclaimer)
        .where(Disclaimer.type == row.type, Disclaimer.active.is_(True), Disclaimer.version != version)
        .values(active=False, effective_to=now)
    )
    row.active = True
    row.effective_from = now
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ActivationConflictError(version) from exc

    effective_from_iso = now.isoformat()

    # Best-effort R2 HTML snapshot — source of truth is the committed DB row.
    snapshot_key: Optional[str] = None
    snapshot_status: str
    try:
        safe_content = _html.escape(row.content)
        html_doc = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>Disclaimer {_html.escape(version)}</title></head><body>"
            f"<p>{safe_content}</p>"
            f"<footer><small>version: {_html.escape(version)} | "
            f"type: {_html.escape(row.type)} | "
            f"activated_at: {_html.escape(effective_from_iso)}</small></footer>"
            "</body></html>"
        )
        _key = f"disclaimers/{row.type}/{version}.html"
        storage.put_object(_key, html_doc.encode("utf-8"), "text/html; charset=utf-8")
        snapshot_key = _key
        snapshot_status = "ok"
    except storage.StorageNotConfigured:
        snapshot_status = "skipped_r2_unconfigured"
    except Exception:  # noqa: BLE001 — R2 failure must not roll back a committed activation
        logger.exception("compliance: R2 snapshot failed for disclaimer version=%s", version)
        snapshot_status = "failed"

    # Best-effort Redis cache flush — a Redis blip must never fail the activation.
    try:
        await get_redis().delete(f"{_DISCLAIMER_CACHE_PREFIX}{row.type}")
    except Exception:  # noqa: BLE001
        logger.debug("compliance: Redis flush failed after activating disclaimer %s", version)

    return {
        "version": version,
        "type": row.type,
        "active": True,
        "effective_from": effective_from_iso,
        "snapshot_status": snapshot_status,
        "snapshot_key": snapshot_key,
    }


def _snapshot_from_rows(rows: Any) -> dict:
    """Group audit rows into ``{date_iso: {key: label}}`` — pure, no DB.

    Caller must sort rows by ``served_at`` ASC before passing. Within each UTC
    calendar date, the key is ``str(user_id)`` when present, falling back to
    ``session_id``, then ``request_id``, then ``content_hash``. Later rows (ASC
    order) overwrite earlier ones for the same key on the same date, so the
    snapshot captures the *latest* label seen per subject per day.
    """
    result: dict = {}
    for row in rows:
        date_key = row.served_at.astimezone(timezone.utc).date().isoformat()
        if row.user_id is not None:
            subject = str(row.user_id)
        elif row.session_id:
            subject = row.session_id
        elif row.request_id:
            subject = row.request_id
        else:
            subject = row.content_hash
        if date_key not in result:
            result[date_key] = {}
        result[date_key][subject] = row.label
    return result


async def label_churn_review(db: Any, *, recommendation_type: str = "educational_label") -> dict:
    """Compute label churn between the two most-recent audit batch days.

    The churn universe is keyed by served subject (user_id, falling back to
    session/request id) over the two most recent UTC days that have audited
    labels — a documented PROXY until a dedicated instrument-universe
    batch-snapshot table lands with B28 engine activation. Reuses the canonical
    ``governance.review_batch`` (>5 % → hold) and surfaces the hold/publish
    decision to the operator.

    Returns a dict matching ``LabelChurnResponse`` (admin router) and
    ``BatchDecision`` values from ``governance.BatchDecision``.
    """
    from sqlalchemy import select

    from dhanradar.models.compliance import AiRecommendationAudit
    from dhanradar.scoring.engine import governance

    # Validate the type against the SAME positive allowlist the audit writer uses
    # (non-neg #1). Without this, an unrecognized/advisory type silently returns
    # `insufficient_data` + `requires_human_review=False` — a fail-open signal if a
    # downstream operator script gates on that boolean for an invalid input.
    if recommendation_type not in _ALLOWED_TYPES:
        raise ValueError(
            f"unknown recommendation_type {recommendation_type!r}; "
            f"valid types: {sorted(_ALLOWED_TYPES)}"
        )

    rows = (
        await db.scalars(
            select(AiRecommendationAudit)
            .where(AiRecommendationAudit.recommendation_type == recommendation_type)
            .order_by(AiRecommendationAudit.served_at.asc())
        )
    ).all()

    snapshots = _snapshot_from_rows(rows)
    sorted_days = sorted(snapshots.keys())

    _insufficient = {
        "recommendation_type": recommendation_type,
        "previous_day": None,
        "current_day": sorted_days[-1] if sorted_days else None,
        "universe": len(snapshots[sorted_days[-1]]) if sorted_days else 0,
        "changed": 0,
        "churn": 0.0,
        "threshold": governance.DEFAULT_CHURN_THRESHOLD,
        "decision": "insufficient_data",
        "requires_human_review": False,
        "distribution_violations": [],
        "reason": "need >=2 batch days of audited labels",
    }

    if len(sorted_days) < 2:
        return _insufficient

    prev_day = sorted_days[-2]
    curr_day = sorted_days[-1]
    prev = snapshots[prev_day]
    curr = snapshots[curr_day]

    review = governance.review_batch(prev, curr)
    changed = sum(1 for k in curr if k in prev and curr[k] != prev[k])

    return {
        "recommendation_type": recommendation_type,
        "previous_day": prev_day,
        "current_day": curr_day,
        "universe": len(curr),
        "changed": changed,
        "churn": review.churn,
        "threshold": governance.DEFAULT_CHURN_THRESHOLD,
        "decision": review.decision.value,
        "requires_human_review": review.decision is governance.BatchDecision.hold,
        "distribution_violations": review.distribution_violations,
        "reason": review.reason,
    }


async def log_low_confidence(
    *,
    surface: Optional[str] = None,
    confidence_score: Optional[float] = None,
    confidence_band: Optional[str] = None,
    model: Optional[str] = None,
    reason: Optional[str] = None,
    identifier: Optional[str] = None,
    request_id: Optional[str] = None,
) -> bool:
    """Fire-and-forget insert of one low-confidence event log row.

    No writer wired yet — the AI/scoring confidence-floor consumer (B22) calls
    this; built ahead like B20's call site. Opens its own session and NEVER
    raises — on any failure, logs and returns False.
    """
    try:
        from dhanradar.db import TaskSessionLocal
        from dhanradar.models.compliance import AiLowConfidenceLog

        async with TaskSessionLocal() as db:
            db.add(
                AiLowConfidenceLog(
                    surface=surface,
                    identifier=identifier,
                    confidence_score=confidence_score,
                    confidence_band=confidence_band,
                    model=model,
                    reason=reason,
                    request_id=request_id,
                )
            )
            await db.commit()
        return True
    except Exception:  # noqa: BLE001 — fire-and-forget: never breaks the caller
        logger.exception(
            "compliance: low-confidence log write failed surface=%s", surface
        )
        return False


async def is_engine_version_activated(db: Any, model_version: str) -> bool:
    """The rating_engine_changelog registry is the authoritative runtime activation
    state for a scoring model_version (B6/B28).

    Returns True iff a RatingEngineChangelog row exists with the given model_version
    AND activated is True.
    """
    from sqlalchemy import select

    from dhanradar.models.compliance import RatingEngineChangelog

    result = await db.scalar(
        select(RatingEngineChangelog.id)
        .where(
            RatingEngineChangelog.model_version == model_version,
            RatingEngineChangelog.activated.is_(True),
        )
        .limit(1)
    )
    return result is not None


async def list_engine_versions(db: Any, limit: int = 50) -> list[dict]:
    """Return RatingEngineChangelog rows ordered newest-first (by created_at desc).

    Used by the Admin Phase 3 scoring-read endpoint — read-only, no mutations.
    """
    from sqlalchemy import select

    from dhanradar.models.compliance import RatingEngineChangelog

    rows = (
        await db.scalars(
            select(RatingEngineChangelog)
            .order_by(RatingEngineChangelog.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "model_version": r.model_version,
            "created_by": r.created_by,
            "approved_by": r.approved_by,
            "two_person_ok": r.two_person_ok,
            "activated": r.activated,
            "activated_at": r.activated_at.isoformat() if r.activated_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "backtest": getattr(r, "backtest", None),
            "drift": getattr(r, "drift", None),
        }
        for r in rows
    ]


async def safety_monitor_summary(db: Any, *, days: int = 7) -> dict:
    """Read-only safety monitoring summary for the Admin AI Ops console.

    Counts from ``compliance.ai_recommendation_audit`` grouped by
    recommendation_type + confidence_band over the last ``days`` calendar days.

    Returns:
        served_by_type    : dict[str, int]  — total rows per recommendation_type
        by_confidence_band: dict[str, int]  — total rows per confidence_band
        low_confidence_count: int           — rows in ai_low_confidence_log
        recent_audit_rows : list[dict]      — last 10 audit rows (subset of columns)
        recent_low_confidence: list[dict]   — last 10 low-confidence log rows
    """
    from datetime import timedelta

    from sqlalchemy import func, select

    from dhanradar.models.compliance import AiLowConfidenceLog, AiRecommendationAudit

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Count by recommendation_type
    type_rows = (
        await db.execute(
            select(
                AiRecommendationAudit.recommendation_type,
                func.count().label("cnt"),
            )
            .where(AiRecommendationAudit.served_at >= cutoff)
            .group_by(AiRecommendationAudit.recommendation_type)
        )
    ).all()
    served_by_type: dict[str, int] = {r.recommendation_type: r.cnt for r in type_rows}

    # Count by confidence_band
    band_rows = (
        await db.execute(
            select(
                AiRecommendationAudit.confidence_band,
                func.count().label("cnt"),
            )
            .where(AiRecommendationAudit.served_at >= cutoff)
            .group_by(AiRecommendationAudit.confidence_band)
        )
    ).all()
    by_confidence_band: dict[str, int] = {
        (r.confidence_band or "unknown"): r.cnt for r in band_rows
    }

    # Count low_confidence_log rows
    low_conf_count = (
        await db.scalar(
            select(func.count())
            .select_from(AiLowConfidenceLog)
            .where(AiLowConfidenceLog.logged_at >= cutoff)
        )
    ) or 0

    # Recent audit rows (last 10)
    recent_audit = (
        await db.scalars(
            select(AiRecommendationAudit)
            .where(AiRecommendationAudit.served_at >= cutoff)
            .order_by(AiRecommendationAudit.served_at.desc())
            .limit(10)
        )
    ).all()

    recent_audit_rows = [
        {
            "id": str(r.id),
            "served_at": r.served_at.isoformat() if r.served_at else None,
            "recommendation_type": r.recommendation_type,
            "label": r.label,
            "confidence_band": r.confidence_band,
            "model": r.model,
            "surface": r.surface,
            "prompt_version": r.prompt_version,
            "request_id": r.request_id,
        }
        for r in recent_audit
    ]

    # Recent low-confidence rows (last 10)
    recent_lc = (
        await db.scalars(
            select(AiLowConfidenceLog)
            .where(AiLowConfidenceLog.logged_at >= cutoff)
            .order_by(AiLowConfidenceLog.logged_at.desc())
            .limit(10)
        )
    ).all()

    recent_low_confidence = [
        {
            "id": str(r.id),
            "logged_at": r.logged_at.isoformat() if r.logged_at else None,
            "surface": r.surface,
            "identifier": r.identifier,
            "confidence_score": r.confidence_score,
            "confidence_band": r.confidence_band,
            "model": r.model,
            "reason": r.reason,
            "request_id": r.request_id,
        }
        for r in recent_lc
    ]

    return {
        "days": days,
        "served_by_type": served_by_type,
        "by_confidence_band": by_confidence_band,
        "low_confidence_count": low_conf_count,
        "recent_audit_rows": recent_audit_rows,
        "recent_low_confidence": recent_low_confidence,
    }


async def list_distinct_prompt_versions(db: Any, *, limit: int = 20) -> list[str]:
    """Return distinct prompt_version values seen in ``compliance.ai_recommendation_audit``.

    Used by the AI Ops Prompt & RAG page (Phase 4) to surface which prompt_version
    tags have been used — the registry is the gateway caller's responsibility; this
    query is a derived view over the audit trail only.

    Returns a list of non-null, non-empty prompt_version strings, ordered by first
    seen (ascending) so the newest version appears last. Limit defaults to 20.
    """
    from sqlalchemy import distinct, select

    from dhanradar.models.compliance import AiRecommendationAudit

    rows = (
        await db.scalars(
            select(distinct(AiRecommendationAudit.prompt_version))
            .where(AiRecommendationAudit.prompt_version.isnot(None))
            .where(AiRecommendationAudit.prompt_version != "")
            .order_by(AiRecommendationAudit.prompt_version.asc())
            .limit(limit)
        )
    ).all()
    return list(rows)


async def record_engine_changelog(
    db: Any,
    *,
    model_version: str,
    created_by: str,
    approved_by: Optional[str],
    factors_before: dict,
    factors_after: dict,
    methodology_url: Optional[str],
    activated: bool = False,
    activated_at: Optional[datetime] = None,
    backtest: Optional[dict] = None,
    drift: Optional[dict] = None,
) -> dict:
    """Insert one scoring/rating methodology changelog row.

    Computes ``two_person_ok`` via ``governance.two_person_gate_ok`` (documented
    gate; non-blocking at this stage — enforced at activation time). Written by
    the B6/B28 two-person scoring-activation gate (slice 2) — built ahead; no
    caller yet.
    """
    from dhanradar.models.compliance import RatingEngineChangelog
    from dhanradar.scoring.engine import governance

    two_person_ok = governance.two_person_gate_ok(created_by, approved_by)
    row = RatingEngineChangelog(
        model_version=model_version,
        created_by=created_by,
        approved_by=approved_by,
        two_person_ok=two_person_ok,
        factors_before=factors_before,
        factors_after=factors_after,
        methodology_url=methodology_url,
        activated=activated,
        activated_at=activated_at,
        backtest=backtest,
        drift=drift,
    )
    db.add(row)
    await db.commit()
    return {
        "id": str(row.id),
        "model_version": row.model_version,
        "created_by": row.created_by,
        "approved_by": row.approved_by,
        "two_person_ok": row.two_person_ok,
        "factors_before": row.factors_before,
        "factors_after": row.factors_after,
        "methodology_url": row.methodology_url,
        "activated": row.activated,
        "activated_at": row.activated_at.isoformat() if row.activated_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "backtest": getattr(row, "backtest", None),
        "drift": getattr(row, "drift", None),
    }


# ---------------------------------------------------------------------------
# AI output feedback — user thumbs up/down on served AI outputs
# ---------------------------------------------------------------------------


class DuplicateFeedbackError(Exception):
    """Raised when a user submits feedback for an audit_id they already rated."""

    def __init__(self, audit_id: str, user_id: str) -> None:
        super().__init__(f"feedback already submitted: audit={audit_id} user={user_id}")


async def record_feedback(
    db: Any,
    *,
    audit_id: str,
    user_id: str,
    helpful: bool,
    feedback_text: Optional[str] = None,
) -> dict:
    """Append one user-feedback row. Append-only — no updates or deletes.

    ``audit_id`` and ``user_id`` are validated as UUID strings on entry
    (raises ``ValueError`` on bad format → FastAPI renders 422).

    DPDP: ``user_id`` is stored — ``RequireConsent`` must be wired to the
    calling endpoint before this function is invoked with real-user data
    (tracked in BLOCKERS.md B64).

    Returns the created row as a dict.
    """
    import uuid

    from dhanradar.models.compliance import AiOutputFeedback

    # Validate UUID format early — raises ValueError (→ 422) on bad input.
    audit_uuid = uuid.UUID(audit_id)
    user_uuid = uuid.UUID(user_id)

    from sqlalchemy.exc import IntegrityError

    row = AiOutputFeedback(
        audit_id=audit_uuid,
        user_id=user_uuid,
        helpful=helpful,
        feedback_text=feedback_text,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise DuplicateFeedbackError(audit_id, user_id)
    # user_id intentionally omitted from the returned dict (DPDP).
    return {
        "id": str(row.id),
        "audit_id": str(row.audit_id),
        "helpful": row.helpful,
        "feedback_text": row.feedback_text,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def feedback_summary(db: Any, *, days: int = 30) -> dict:
    """Return aggregate feedback stats for the admin AI Ops console.

    Returns total count, helpful count, helpful_pct, and the last 20 rows
    within the requested window.
    """
    import datetime

    from sqlalchemy import func, select

    from dhanradar.models.compliance import AiOutputFeedback

    since = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=days)

    total = (
        await db.scalar(
            select(func.count()).select_from(AiOutputFeedback).where(
                AiOutputFeedback.created_at >= since
            )
        )
    ) or 0

    helpful = (
        await db.scalar(
            select(func.count()).select_from(AiOutputFeedback).where(
                AiOutputFeedback.created_at >= since,
                AiOutputFeedback.helpful.is_(True),
            )
        )
    ) or 0

    recent_rows = (
        await db.scalars(
            select(AiOutputFeedback)
            .where(AiOutputFeedback.created_at >= since)
            .order_by(AiOutputFeedback.created_at.desc())
            .limit(20)
        )
    ).all()

    return {
        "total": total,
        "helpful": helpful,
        "helpful_pct": round(helpful / total * 100, 1) if total else None,
        "recent": [
            {
                "id": str(r.id),
                "audit_id": str(r.audit_id),
                "helpful": r.helpful,
                "feedback_text": r.feedback_text,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recent_rows
        ],
    }
