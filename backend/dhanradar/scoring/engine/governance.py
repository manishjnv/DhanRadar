"""
DhanRadar — rating-engine governance (spec §7 / architecture §S4).

Pure, deterministic governance checks (fail-closed):

  * batch churn gate: > 5% of the universe changing label in one batch ⇒ the
    batch is HELD in ``pending_publish`` for Compliance human review (prevents a
    methodology bug or a market shock from silently relabelling everyone);
  * label-distribution sanity: no single label may exceed a max share (prevents
    an all-🔴 collapse in a crash from publishing);
  * two-person methodology gate: a weight/band/normalization change requires
    ``approved_by`` set AND ``approved_by != created_by`` (B6 — documented now,
    enforced before a version is ACTIVATED in production);
  * changelog entry shape for every methodology change (factors before/after +
    methodology URL), required for regulatory reproducibility (spec §8).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_CHURN_THRESHOLD = 0.05  # >5% of the universe → hold
DEFAULT_MAX_LABEL_SHARE = 0.80  # no single label may exceed 80% of a batch


class BatchDecision(str, enum.Enum):
    publish = "publish"
    hold = "pending_publish"  # held for Compliance review (fail-closed)


@dataclass(frozen=True)
class BatchReview:
    decision: BatchDecision
    churn: float
    distribution_violations: list[str] = field(default_factory=list)
    reason: str = ""


def batch_churn(previous: dict[str, str], current: dict[str, str]) -> float:
    """Fraction of instruments (present in BOTH snapshots) whose label changed."""
    common = [k for k in current if k in previous]
    if not common:
        return 0.0
    changed = sum(1 for k in common if current[k] != previous[k])
    return changed / len(common)


def distribution_violations(
    current: dict[str, str], max_share: float = DEFAULT_MAX_LABEL_SHARE
) -> list[str]:
    if not current:
        return []
    n = len(current)
    counts: dict[str, int] = {}
    for label in current.values():
        counts[label] = counts.get(label, 0) + 1
    return [
        f"{label}={count / n:.0%} > max {max_share:.0%}"
        for label, count in counts.items()
        if count / n > max_share
    ]


def review_batch(
    previous: dict[str, str],
    current: dict[str, str],
    *,
    churn_threshold: float = DEFAULT_CHURN_THRESHOLD,
    max_label_share: float = DEFAULT_MAX_LABEL_SHARE,
) -> BatchReview:
    """Decide whether a batch may auto-publish or must be HELD for Compliance.
    Fail-closed: either gate tripping → hold."""
    churn = batch_churn(previous, current)
    violations = distribution_violations(current, max_label_share)
    if churn > churn_threshold or violations:
        reasons = []
        if churn > churn_threshold:
            reasons.append(f"churn {churn:.1%} > {churn_threshold:.0%}")
        if violations:
            reasons.append("distribution: " + "; ".join(violations))
        return BatchReview(BatchDecision.hold, churn, violations, "; ".join(reasons))
    return BatchReview(BatchDecision.publish, churn, [], "within bounds")


class TwoPersonGateError(ValueError):
    """A methodology change failed the two-person gate (approved_by ≠ created_by)."""


def two_person_gate_ok(created_by: Optional[str], approved_by: Optional[str]) -> bool:
    return bool(approved_by) and approved_by != created_by


def make_changelog_entry(
    *,
    model_version: str,
    created_by: str,
    approved_by: Optional[str],
    factors_before: dict,
    factors_after: dict,
    methodology_url: str,
    enforce_two_person: bool = False,
) -> dict:
    """Build a reproducibility changelog entry for a methodology change.

    With ``enforce_two_person=True`` (production activation), raises
    TwoPersonGateError unless ``approved_by`` is set and differs from
    ``created_by`` (B6). Documented-but-non-blocking until activation."""
    if enforce_two_person and not two_person_gate_ok(created_by, approved_by):
        raise TwoPersonGateError(
            "methodology change requires approved_by set and != created_by "
            f"(created_by={created_by!r}, approved_by={approved_by!r})"
        )
    return {
        "model_version": model_version,
        "created_by": created_by,
        "approved_by": approved_by,
        "factors_before": factors_before,
        "factors_after": factors_after,
        "methodology_url": methodology_url,
        "two_person_ok": two_person_gate_ok(created_by, approved_by),
    }
