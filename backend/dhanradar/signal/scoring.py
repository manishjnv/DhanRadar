"""
DhanRadar — Signal scoring engine (server-only).

NON-NEGOTIABLE #2 COMPLIANCE: The factor weights (NIFTY_WEIGHT, VIX_WEIGHT,
BREADTH_WEIGHT) and the intermediate weighted aggregate are SERVER-ONLY constants.
They are intentionally absent from every return type and every response schema.
They must NEVER be serialised to the client in any form.

This module is the single source of truth for signal scoring logic.  The same
computation previously lived in the browser (frontend/src/features/signal/
SignalPage.tsx) where factor weights leaked into the JS bundle — this module
removes that leak.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Server-only weights (never serialised — non-neg #2)
# ---------------------------------------------------------------------------

NIFTY_WEIGHT: float = 0.20
VIX_WEIGHT: float = 0.40
BREADTH_WEIGHT: float = 0.40

# Sanity-check: weights must sum to 1.0 at import time.
assert abs(NIFTY_WEIGHT + VIX_WEIGHT + BREADTH_WEIGHT - 1.0) < 1e-9, (
    "Signal scoring weights must sum to 1.0"
)


# ---------------------------------------------------------------------------
# Per-axis scoring functions (ported exactly from SignalPage.tsx)
# ---------------------------------------------------------------------------

def nifty_score(change_pct: float) -> int:
    """Map Nifty 50 daily change-% to a stress score 0–4.

    Bands (ported verbatim from SignalPage.tsx::niftyScore):
      change_pct >  0.0  → 0  (positive — no stress)
      change_pct > -2.0  → 1
      change_pct > -5.0  → 2
      change_pct > -8.0  → 3
      else               → 4  (severe decline)
    """
    if change_pct > 0:
        return 0
    if change_pct > -2:
        return 1
    if change_pct > -5:
        return 2
    if change_pct > -8:
        return 3
    return 4


def vix_score(vix: float) -> int:
    """Map India VIX level to a stress score 0–4.

    Bands (ported verbatim from SignalPage.tsx::vixScore):
      vix < 15  → 0  (calm)
      vix < 17  → 1
      vix < 19  → 2
      vix < 22  → 3
      else      → 4  (extreme fear)
    """
    if vix < 15:
        return 0
    if vix < 17:
        return 1
    if vix < 19:
        return 2
    if vix < 22:
        return 3
    return 4


def breadth_score(ad_ratio: float) -> int:
    """Map advances/declines ratio to a stress score 0–4.

    Bands (ported verbatim from SignalPage.tsx::breadthScore):
      ad_ratio > 1.5  → 0  (broad advance)
      ad_ratio > 1.2  → 1
      ad_ratio > 0.8  → 2
      ad_ratio > 0.5  → 3
      else            → 4  (broad decline)
    """
    if ad_ratio > 1.5:
        return 0
    if ad_ratio > 1.2:
        return 1
    if ad_ratio > 0.8:
        return 2
    if ad_ratio > 0.5:
        return 3
    return 4


# ---------------------------------------------------------------------------
# Aggregate computation
# ---------------------------------------------------------------------------

def compute_signal_state(
    nifty_change_pct: float,
    vix_value: float,
    ad_ratio: float,
) -> tuple[int, int, int, str]:
    """Compute per-axis scores and the resulting signal state.

    The weighted aggregate and the factor weights are computed internally and
    are NEVER returned (non-neg #2).

    Returns a 4-tuple: (nifty_score, vix_score, breadth_score, state)
      state ∈ {'triggered', 'watch', 'no_signal'}

    Thresholds (ported exactly from SignalPage.tsx):
      weighted >= 3.0 → 'triggered'
      weighted >= 2.0 → 'watch'
      else            → 'no_signal'
    """
    ns = nifty_score(nifty_change_pct)
    vs = vix_score(vix_value)
    bs = breadth_score(ad_ratio)

    # Weighted aggregate — intentionally not returned (server-side only).
    _weighted = ns * NIFTY_WEIGHT + vs * VIX_WEIGHT + bs * BREADTH_WEIGHT

    if _weighted >= 3.0:
        state = "triggered"
    elif _weighted >= 2.0:
        state = "watch"
    else:
        state = "no_signal"

    return ns, vs, bs, state
