"""
DhanRadar — MF peer-cohort benchmark + category-relative comparison (B58).

Pure module: turns a category's peer NAV-derived returns into a median benchmark,
and compares one fund's own returns against that benchmark to produce the
category-relative label inputs (:class:`~dhanradar.mf.signals.CategoryRelative`).
No DB / network / Redis / Celery imports — golden-set testable.  The DB query that
loads peer NAV series and calls these functions lives in ``tasks/mf.py``
(``_compute_cohort``); this file is the math only.

Semantics (FINAL_SCORING_SPEC §4.1 — the LABEL rule is category-relative):
  * benchmark   = the MEDIAN of same-category peers' 1Y / 3Y returns + max-drawdown.
                  Median (not mean) so a few extreme funds do not move the cohort.
  * a fund "outperforms" only when it beats the cohort median by more than a margin;
    "underperforms" only when it trails by more than the margin; inside the band it
    is "matching category" → on_track.  The margin keeps a basis-point gap around
    the median from flipping ~half of every category to off_track.
  * out_of_form additionally needs a ``structural_concern`` (fundamentals we do not
    yet ingest), so ``sustained_underperformance`` alone is necessary-not-sufficient
    — out_of_form stays honestly unreachable until structural signals exist.

All thresholds are PROVISIONAL v1 heuristics — every engine result is tagged
``provisional_model`` until the backtest + two-person activation gate (B6 / B28).
The peer set includes the fund itself; with ≥ ``_MIN_COHORT_PEERS`` peers the
self-inclusion bias on a median is negligible and standard for category-relative
ranking.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from dhanradar.mf.signals import CategoryRelative

# ---------------------------------------------------------------------------
# Tunables (provisional v1 — not frozen; see module docstring / B6)
# ---------------------------------------------------------------------------

# A category needs at least this many peers with a usable 1Y return before we
# trust its median as a benchmark.  Fewer → benchmark withheld → on_track (honest:
# we cannot assert a category position from a tiny, noisy cohort).
_MIN_COHORT_PEERS = 5

# A fund must beat / trail the cohort median by MORE than this many return
# percentage points to count as out / under-performing; inside the band it is
# "matching category" (on_track).
_MARGIN_PCT = 2.0

# Per-fund long-horizon stats: (return_1y_pct, return_3y_pct, max_drawdown_pct);
# any component may be None (insufficient history for that window).
FundStats = tuple[float | None, float | None, float | None]


@dataclass(frozen=True)
class CohortBenchmark:
    """Median benchmark for one category.  A None median means the cohort was too
    small / sparse on that window and that comparison is withheld."""

    category: str
    median_return_1y: float | None
    median_return_3y: float | None
    median_max_drawdown: float | None
    n_peers: int


def _median_or_none(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def build_benchmark(category: str, peer_stats: list[FundStats]) -> CohortBenchmark:
    """Aggregate same-category peers' long-horizon stats into median benchmarks.

    Each window is aggregated independently over the peers that HAVE that window
    (a young fund with no 3Y return still contributes its 1Y return).  When fewer
    than ``_MIN_COHORT_PEERS`` peers have a 1Y return the whole benchmark is
    withheld (all medians None) — too thin to trust.
    """
    rets_1y = [s[0] for s in peer_stats if s[0] is not None]
    rets_3y = [s[1] for s in peer_stats if s[1] is not None]
    dds = [s[2] for s in peer_stats if s[2] is not None]
    n_peers = len(rets_1y)
    if n_peers < _MIN_COHORT_PEERS:
        return CohortBenchmark(category, None, None, None, n_peers)
    return CohortBenchmark(
        category=category,
        median_return_1y=_median_or_none(rets_1y),
        median_return_3y=_median_or_none(rets_3y),
        median_max_drawdown=_median_or_none(dds),
        n_peers=n_peers,
    )


def compare_to_cohort(own: FundStats, benchmark: CohortBenchmark | None) -> CategoryRelative:
    """Compare one fund's long-horizon stats to its category benchmark → the
    category-relative LABEL inputs.  Returns an all-False :class:`CategoryRelative`
    (→ on_track) whenever the comparison cannot be made honestly (no benchmark,
    withheld median, or the fund lacks that window).  Context strings are
    educational + comparative — never numeric, never advisory (non-neg #1/#2)."""
    if benchmark is None:
        return CategoryRelative()
    if benchmark.median_return_1y is None:
        # Cohort too thin to benchmark — assert no category position, but tell the
        # user WHY it is unlabelled vs genuinely matching peers (explainability).
        return CategoryRelative(
            contributing=["category peer benchmark unavailable — too few comparable funds to compare"]
        )

    own_1y, own_3y, own_dd = own
    med_1y = benchmark.median_return_1y
    med_3y = benchmark.median_return_3y
    med_dd = benchmark.median_max_drawdown

    def _ahead(value: float | None, median: float | None) -> bool:
        return value is not None and median is not None and value > median + _MARGIN_PCT

    def _behind(value: float | None, median: float | None) -> bool:
        return value is not None and median is not None and value < median - _MARGIN_PCT

    outperform_1y = _ahead(own_1y, med_1y)
    outperform_3y = _ahead(own_3y, med_3y)
    underperform_1y = _behind(own_1y, med_1y)
    underperform_3y = _behind(own_3y, med_3y)
    # Drawdown is "controlled" when no deeper than the typical category peer.
    drawdown_controlled = own_dd is not None and med_dd is not None and own_dd <= med_dd

    underperform_12m = underperform_1y
    sustained_underperformance = underperform_1y and underperform_3y

    contributing: list[str] = []
    contradicting: list[str] = []
    if outperform_1y and own_3y is None:
        # Ahead on 1Y but no 3-year history → cannot reach in_form; say so plainly
        # so a strong young fund is not silently held at on_track (explainability).
        contributing.append(
            "ahead of category peers over the past year; three-year track record not yet established"
        )
    elif outperform_1y:
        contributing.append("ahead of category peers over the past year")
    if outperform_3y:
        contributing.append("ahead of category peers over three years")
    if drawdown_controlled:
        contributing.append("drawdown contained versus category peers")
    if underperform_12m:
        contradicting.append("behind category peers over the trailing 12 months")
    if sustained_underperformance:
        # Factual 3Y context — kept escalation-free: this state maps to off_track
        # (out_of_form needs a structural concern we do not yet ingest), so the
        # phrasing must not read as the most-severe label (Compliance B58 cond-1).
        contradicting.append("also behind category peers over three years")

    return CategoryRelative(
        outperform_1y=outperform_1y,
        outperform_3y=outperform_3y,
        drawdown_controlled=drawdown_controlled,
        underperform_12m=underperform_12m,
        sustained_underperformance=sustained_underperformance,
        contributing=contributing,
        contradicting=contradicting,
    )
