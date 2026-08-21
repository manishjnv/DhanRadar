"""Pure watchlist-alert trigger helpers (P2 backend, no I/O).

Two trigger types:
  nav_move     — 1-day NAV move >= +/-2% (uses existing mf_nav_history).
  label_change — verb_label differs from the previous rank row (uses
                 existing mf_fund_ranks; never recomputes the score).

Both helpers are side-effect-free so they can be unit-tested without a DB.
"""

from __future__ import annotations

_NAV_MOVE_THRESHOLD_PCT: float = 2.0

# Educational label order (non-neg #1) — NOT advisory verbs.
_VALID_LABELS: frozenset[str] = frozenset(
    {"in_form", "on_track", "off_track", "out_of_form", "insufficient_data"}
)


def nav_move_pct(nav_today: float, nav_yesterday: float) -> float | None:
    """1-day percentage move. Returns None when yesterday is zero/missing."""
    if not nav_yesterday:
        return None
    return ((nav_today - nav_yesterday) / nav_yesterday) * 100.0


def should_fire_nav_move(nav_today: float, nav_yesterday: float) -> bool:
    """True when the absolute 1-day move >= _NAV_MOVE_THRESHOLD_PCT."""
    pct = nav_move_pct(nav_today, nav_yesterday)
    if pct is None:
        return False
    return abs(pct) >= _NAV_MOVE_THRESHOLD_PCT


def should_fire_label_change(old_label: str, new_label: str) -> bool:
    """True when two valid, non-identical educational labels differ.

    insufficient_data on either side is excluded — a fund going into or
    out of an unrateable state is not a meaningful label transition.
    """
    if old_label == new_label:
        return False
    if old_label not in _VALID_LABELS or new_label not in _VALID_LABELS:
        return False
    if "insufficient_data" in (old_label, new_label):
        return False
    return True


def nav_alert_copy(isin: str, fund_name: str, pct: float) -> tuple[str, str]:
    """Return (title, body) for a nav_move alert. Educational, no advisory verbs."""
    direction = "up" if pct >= 0 else "down"
    abs_pct = abs(pct)
    title = f"{fund_name} NAV moved {direction} {abs_pct:.1f}%"
    body = (
        f"{fund_name} ({isin}) NAV moved {direction} {abs_pct:.1f}% today. "
        "This is a factual NAV data point. "
        "NOT INVESTMENT ADVICE. Past movement does not predict future performance."
    )
    return title, body


def label_alert_copy(
    isin: str, fund_name: str, old_label: str, new_label: str, confidence_band: str | None
) -> tuple[str, str]:
    """Return (title, body) for a label_change alert. Educational, no advisory verbs."""
    band_note = f" (confidence: {confidence_band})" if confidence_band else ""
    title = f"{fund_name} label updated: {old_label} → {new_label}"
    body = (
        f"{fund_name} ({isin}) fund label changed from \"{old_label}\" "
        f"to \"{new_label}\"{band_note} in the latest nightly ranking run. "
        "Labels describe relative performance within the fund's peer group. "
        "NOT INVESTMENT ADVICE. For educational purposes only."
    )
    return title, body
