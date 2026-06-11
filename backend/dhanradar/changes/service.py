"""
DhanRadar — What Changed service (Plan Group 2).

READ-ONLY over persisted tables. Never imports or modifies:
  scoring/engine/*, mf/signals.py, mf/scoring_bridge.py, mf/service.py,
  tasks/*, news/*, insights/*, transparency/*, auth/*, consent/*.

Label/band diffs are derived from the already-persisted
mf.mf_user_fund_score_history rows via get_snapshot_history().
NAV freshness is derived from MAX(mf_nav_history.nav_date) per ISIN.
unified_score is NEVER selected — it does not exist in MfUserFundScoreHistory.

SEBI educational boundary: all copy is DESCRIPTIVE (category-relative form),
never advisory. FORBIDDEN substrings in any reason string:
  buy, sell, hold, switch, reduce, rebalance, redeem, exit, book,
  consider, recommend, should, suggest, avoid, caution, opportunity,
  "take action".
  "improved"/"weakened" describe only the LABEL/band, never an instruction.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.changes.schemas import FundChange
from dhanradar.mf.history import get_snapshot_history
from dhanradar.models.mf import MfFund, MfNavHistory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rank tables for label and band comparison (quality order).
# Lower index = stronger category-relative form.
# "insufficient_data" is intentionally OFF this scale (handled separately).
# ---------------------------------------------------------------------------

_LABEL_RANK: dict[str, int] = {
    "in_form": 0,
    "on_track": 1,
    "off_track": 2,
    "out_of_form": 3,
}

_BAND_RANK: dict[str, int] = {
    "high": 0,
    "medium": 1,
    "low": 2,
}

# NAV age threshold (calendar days) above which we flag as stale.
# Mirrors transparency._STALE_THRESHOLD_DAYS; not imported (locked lane).
_NAV_STALE_DAYS = 5


# ---------------------------------------------------------------------------
# Pure classification logic — no DB, fully testable in isolation
# ---------------------------------------------------------------------------


def classify_change(
    label_from: str | None,
    band_from: str | None,
    label_to: str,
    band_to: str,
) -> tuple[str, bool, list[str]]:
    """Classify the label/band transition for one fund.

    Returns (change_kind, changed, reasons).

    change_kind is one of:
      "improved" | "weakened" | "unchanged" | "new" | "insufficient_data"

    changed is True when label_from != label_to (or a meaningful data-state change).

    reasons is a list of EDUCATIONAL, non-advisory plain-language strings.
    NEVER uses advisory verbs.
    """
    reasons: list[str] = []

    # --- Case 1: single snapshot (no prior) ---
    if label_from is None:
        return (
            "new",
            False,
            [
                "This is the first labelled snapshot for this fund, "
                "so there is no earlier snapshot to compare against."
            ],
        )

    # --- Case 2: latest is insufficient_data ---
    if label_to == "insufficient_data":
        return (
            "insufficient_data",
            label_from != label_to,
            ["The latest snapshot does not have enough data to assign a label."],
        )

    # --- Case 3: prior was insufficient_data ---
    if label_from == "insufficient_data":
        return (
            "insufficient_data",
            True,
            [
                "The earlier snapshot did not have enough data to assign a label, "
                "so this is the first comparable assessment."
            ],
        )

    # --- Case 4: both snapshots have real labels ---
    to_rank = _LABEL_RANK[label_to]
    from_rank = _LABEL_RANK[label_from]
    changed = label_from != label_to

    if to_rank < from_rank:
        kind = "improved"
        reasons.append(
            f"The label moved from {label_from} to {label_to}, "
            "a stronger category-relative form than the previous snapshot."
        )
    elif to_rank > from_rank:
        kind = "weakened"
        reasons.append(
            f"The label moved from {label_from} to {label_to}, "
            "a weaker category-relative form than the previous snapshot."
        )
    else:
        kind = "unchanged"
        reasons.append(
            f"The label held at {label_to} since the previous snapshot."
        )

    # --- Optional band reason: appended only when both present, both ranked, and differ ---
    if (
        band_from is not None
        and band_from in _BAND_RANK
        and band_to in _BAND_RANK
        and band_from != band_to
    ):
        from_band_rank = _BAND_RANK[band_from]
        to_band_rank = _BAND_RANK[band_to]
        if to_band_rank < from_band_rank:
            reasons.append(
                f"Confidence band strengthened from {band_from} to {band_to}."
            )
        else:
            reasons.append(
                f"Confidence band eased from {band_from} to {band_to}."
            )

    return kind, changed, reasons


# ---------------------------------------------------------------------------
# DB query helpers (read-only)
# ---------------------------------------------------------------------------


async def _fetch_scheme_names(
    db: AsyncSession, isins: list[str]
) -> dict[str, str | None]:
    """Return {isin: scheme_name} from mf.mf_funds."""
    if not isins:
        return {}
    stmt = select(MfFund.isin, MfFund.scheme_name).where(MfFund.isin.in_(isins))
    rows = (await db.execute(stmt)).all()
    return {r.isin: r.scheme_name for r in rows}


async def _fetch_latest_nav_dates(
    db: AsyncSession, isins: list[str]
) -> dict[str, date | None]:
    """Return {isin: max(nav_date)} from mf.mf_nav_history."""
    if not isins:
        return {}
    stmt = (
        select(
            MfNavHistory.isin,
            func.max(MfNavHistory.nav_date).label("latest_nav"),
        )
        .where(MfNavHistory.isin.in_(isins))
        .group_by(MfNavHistory.isin)
    )
    rows = (await db.execute(stmt)).all()
    return {r.isin: r.latest_nav for r in rows}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def build_portfolio_changes(
    db: AsyncSession,
    *,
    user_id: str,
    portfolio_id: str,
) -> list[FundChange]:
    """Build the what-changed payload for a portfolio.

    Ownership check is performed by the router BEFORE calling this function.
    This function only builds the per-fund diff from already-validated inputs.

    Returns an empty list when the portfolio has no history rows (cold-start).
    unified_score is NEVER selected anywhere in this function.
    """
    # --- Fetch snapshot history (date-DESC, already scoped to user+portfolio) ---
    rows = await get_snapshot_history(db, user_id, portfolio_id)

    if not rows:
        return []

    # --- Reshape into per-ISIN date-DESC list of (snapshot_date, verb_label, band) ---
    # rows is: [{"snapshot_date": ISOstr, "funds": [{"isin","verb_label","confidence_band"}]}]
    # We preserve date-DESC order as we append per isin.
    isin_snapshots: dict[str, list[tuple[str, str, str]]] = {}
    for snapshot in rows:
        snap_date = snapshot["snapshot_date"]
        for fund in snapshot["funds"]:
            isin = fund["isin"]
            if isin not in isin_snapshots:
                isin_snapshots[isin] = []
            isin_snapshots[isin].append(
                (snap_date, fund["verb_label"], fund["confidence_band"])
            )

    isins = sorted(isin_snapshots.keys())  # stable order by isin

    # --- Bulk-fetch supporting data ---
    scheme_map = await _fetch_scheme_names(db, isins)
    nav_map = await _fetch_latest_nav_dates(db, isins)

    today = datetime.now(tz=UTC).date()

    # --- Build FundChange per isin ---
    changes: list[FundChange] = []
    for isin in isins:
        snapshots = isin_snapshots[isin]  # date-DESC

        # Latest snapshot (index 0)
        as_of_to, label_to, band_to = snapshots[0]

        # Prior snapshot (index 1) if exists
        if len(snapshots) > 1:
            as_of_from, label_from, band_from = snapshots[1]
        else:
            as_of_from = None
            label_from = None
            band_from = None

        # NAV freshness
        nav_date = nav_map.get(isin)
        nav_as_of: str | None = None
        nav_days_ago: int | None = None
        nav_is_stale = False
        if nav_date is not None:
            nav_as_of = nav_date.isoformat() if hasattr(nav_date, "isoformat") else str(nav_date)
            # nav_date may be a date or datetime depending on DB driver
            if hasattr(nav_date, "date"):
                nav_date_obj = nav_date.date()
            else:
                nav_date_obj = nav_date
            nav_days_ago = (today - nav_date_obj).days
            nav_is_stale = nav_days_ago > _NAV_STALE_DAYS

        # Classify the change
        change_kind, changed, reasons = classify_change(
            label_from, band_from, label_to, band_to
        )

        # Append NAV freshness reason
        if nav_is_stale and nav_days_ago is not None:
            reasons.append(
                f"The latest NAV data for this fund is {nav_days_ago} days old."
            )
        elif nav_as_of is not None:
            reasons.append(f"NAV data is current, as of {nav_as_of}.")
        else:
            reasons.append("NAV data availability for this fund is limited.")

        changes.append(
            FundChange(
                isin=isin,
                scheme_name=scheme_map.get(isin),
                label_from=label_from,
                label_to=label_to,
                band_from=band_from,
                band_to=band_to,
                changed=changed,
                change_kind=change_kind,
                reasons=reasons,
                as_of_from=as_of_from,
                as_of_to=as_of_to,
                nav_as_of=nav_as_of,
                nav_days_ago=nav_days_ago,
                nav_is_stale=nav_is_stale,
            )
        )

    return changes
