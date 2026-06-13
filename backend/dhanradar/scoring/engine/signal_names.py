"""
B27 — Canonical signal-name registry (controlled vocabulary).

This module is the SINGLE authoritative source for every string that may appear
in ``LabelSignals.contributing`` / ``LabelSignals.contradicting`` (and therefore
in ``ScoringResult.contributing_signals`` / ``contradicting_signals`` and in the
public ``FundReportItem``).

Design constraints
------------------
* **No imports from other engine modules** — this file has zero intra-engine
  dependencies so it can never form an import cycle.  mf/* modules already import
  from ``dhanradar.scoring.engine``; adding ``signal_names`` there is safe because
  this file itself imports nothing.
* **Compliance lock** — every phrase in ``SIGNAL_DISPLAY`` is a B58-f1
  compliance-approved display string.  Changing *any* phrase requires a Tier-C
  compliance review (scoring-engine / recommendation-logic).  The exact bytes are
  pinned in ``backend/tests/unit/test_signal_names.py``.
* **API stability** — the public API serialises ``list[str]`` of the display
  phrases unchanged; the enum keys are internal only and never reach a client.

Usage
-----
::

    from dhanradar.scoring.engine.signal_names import display, SignalName

    contributing.append(display(SignalName.COHORT_1Y_AHEAD))
"""

from __future__ import annotations

import enum


class SignalName(enum.StrEnum):
    """Canonical machine keys for every approved contributing/contradicting phrase.

    Key-naming convention: ``<DOMAIN>_<MEANING>``.  Keys are stable identifiers;
    the human-readable phrase lives in ``SIGNAL_DISPLAY`` only.
    """

    # ------------------------------------------------------------------ cohort
    # Thin-cohort explainability (benchmark withheld because < _MIN_COHORT_PEERS).
    COHORT_THIN_BENCHMARK = "COHORT_THIN_BENCHMARK"

    # 1-year outperformance paths.
    COHORT_1Y_AHEAD_SHORT_TRACK = "COHORT_1Y_AHEAD_SHORT_TRACK"   # ahead 1Y, no 3Y history
    COHORT_1Y_AHEAD = "COHORT_1Y_AHEAD"                           # ahead 1Y, 3Y history exists

    # 3-year outperformance.
    COHORT_3Y_AHEAD = "COHORT_3Y_AHEAD"

    # Drawdown discipline.
    COHORT_DRAWDOWN_CONTAINED = "COHORT_DRAWDOWN_CONTAINED"

    # Underperformance.
    COHORT_12M_BEHIND = "COHORT_12M_BEHIND"
    COHORT_3Y_ALSO_BEHIND = "COHORT_3Y_ALSO_BEHIND"

    # ------------------------------------------------------------------ NAV / signals
    NAV_TRAILING_RETURN = "NAV_TRAILING_RETURN"
    NAV_VOLATILITY_DRAWDOWN = "NAV_VOLATILITY_DRAWDOWN"


# ---------------------------------------------------------------------------
# Display map — compliance-approved phrases (B58-f1).
# CHANGING ANY VALUE HERE = Tier-C compliance review required.
# ---------------------------------------------------------------------------

SIGNAL_DISPLAY: dict[SignalName, str] = {
    SignalName.COHORT_THIN_BENCHMARK: (
        "category peer benchmark unavailable — too few comparable funds to compare"
    ),
    SignalName.COHORT_1Y_AHEAD_SHORT_TRACK: (
        "ahead of category peers over the past year; "
        "three-year track record not yet established"
    ),
    SignalName.COHORT_1Y_AHEAD: (
        "ahead of category peers over the past year"
    ),
    SignalName.COHORT_3Y_AHEAD: (
        "ahead of category peers over three years"
    ),
    SignalName.COHORT_DRAWDOWN_CONTAINED: (
        "drawdown contained versus category peers"
    ),
    SignalName.COHORT_12M_BEHIND: (
        "behind category peers over the trailing 12 months"
    ),
    SignalName.COHORT_3Y_ALSO_BEHIND: (
        "also behind category peers over three years"
    ),
    SignalName.NAV_TRAILING_RETURN: (
        "trailing return computed from NAV history"
    ),
    SignalName.NAV_VOLATILITY_DRAWDOWN: (
        "volatility/drawdown computed from NAV history"
    ),
}

# Immutable set of all approved display strings. INTENDED as a server-side
# allow-list to guard the contributing/contradicting seam from stray LLM or
# free-text content — runtime enforcement is a follow-on task (B27 review NIT).
# Today this set is the canonical vocabulary used by producers and pinned in
# tests; it is not yet wired as a runtime filter on the API output path.
CANONICAL_SIGNAL_PHRASES: frozenset[str] = frozenset(SIGNAL_DISPLAY.values())


def display(name: SignalName) -> str:
    """Return the compliance-approved display phrase for a canonical signal key.

    This is the only sanctioned way to produce a contributing/contradicting string.
    Every producer MUST call ``display(SignalName.X)`` rather than inlining a
    literal — the vocabulary is controlled here, not scattered across modules.
    """
    return SIGNAL_DISPLAY[name]
