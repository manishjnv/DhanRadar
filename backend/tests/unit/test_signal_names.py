"""
B27 — Canonical signal-name registry tests.

Covers:
  1. Registry invariants: every SignalName has a display phrase; all phrases are
     unique; the frozenset matches the dict values.
  2. Byte-exact compliance pins for every approved phrase (B58-f1 compliance lock).
     Changing any phrase here requires a Tier-C compliance review.
  3. Producer conformance: driving the cohort relative-computation paths asserts
     that every emitted contributing/contradicting string is in
     CANONICAL_SIGNAL_PHRASES (no free-text can slip through).
  4. signals.py NAV producer conformance: NAV-derived strings are canonical.

No DB / Redis / network.
"""

from __future__ import annotations

import datetime

from dhanradar.mf.cohort import CohortBenchmark, compare_to_cohort
from dhanradar.mf.signals import compute_fund_signals
from dhanradar.scoring.engine.signal_names import (
    CANONICAL_SIGNAL_PHRASES,
    SIGNAL_DISPLAY,
    SignalName,
    display,
)

# ---------------------------------------------------------------------------
# 1. Registry invariants
# ---------------------------------------------------------------------------


def test_every_signal_name_has_a_display_phrase():
    """Every member of the SignalName enum must be in SIGNAL_DISPLAY."""
    missing = [name for name in SignalName if name not in SIGNAL_DISPLAY]
    assert not missing, f"SignalName members without a display phrase: {missing}"


def test_all_display_phrases_are_unique():
    """No two signal names may share the same display string."""
    phrases = list(SIGNAL_DISPLAY.values())
    assert len(phrases) == len(set(phrases)), (
        "Duplicate display phrases found — every SignalName must map to a unique string"
    )


def test_canonical_frozenset_matches_dict_values():
    """CANONICAL_SIGNAL_PHRASES must be exactly the set of SIGNAL_DISPLAY values."""
    assert CANONICAL_SIGNAL_PHRASES == frozenset(SIGNAL_DISPLAY.values())


def test_display_helper_returns_correct_phrase():
    """display(name) is a convenience wrapper around SIGNAL_DISPLAY[name]."""
    for name in SignalName:
        assert display(name) == SIGNAL_DISPLAY[name]


# ---------------------------------------------------------------------------
# 2. Byte-exact compliance pins (B58-f1).
#    WARNING: Changing any assertion here = Tier-C compliance review required.
# ---------------------------------------------------------------------------


class TestCompliancePins:
    """Byte-exact pins for every compliance-approved phrase."""

    def test_cohort_thin_benchmark(self):
        """Pin the thin-cohort explainability phrase."""
        assert display(SignalName.COHORT_THIN_BENCHMARK) == (
            "category peer benchmark unavailable — too few comparable funds to compare"
        )

    def test_cohort_no_canonical_category(self):
        """Pin the no-canonical-SEBI-category phrase (B71)."""
        assert display(SignalName.COHORT_NO_CANONICAL_CATEGORY) == (
            "category peer benchmark unavailable — fund not mapped to a SEBI peer "
            "category; no peer comparison made"
        )

    def test_cohort_1y_ahead_short_track(self):
        """Pin the 1Y-ahead / no 3Y track record phrase."""
        assert display(SignalName.COHORT_1Y_AHEAD_SHORT_TRACK) == (
            "ahead of category peers over the past year; "
            "three-year track record not yet established"
        )

    def test_cohort_1y_ahead(self):
        """Pin the 1Y-ahead phrase (fund has 3Y history)."""
        assert display(SignalName.COHORT_1Y_AHEAD) == (
            "ahead of category peers over the past year"
        )

    def test_cohort_3y_ahead(self):
        """Pin the 3Y-ahead phrase."""
        assert display(SignalName.COHORT_3Y_AHEAD) == (
            "ahead of category peers over three years"
        )

    def test_cohort_drawdown_contained(self):
        """Pin the drawdown-controlled phrase."""
        assert display(SignalName.COHORT_DRAWDOWN_CONTAINED) == (
            "drawdown contained versus category peers"
        )

    def test_cohort_12m_behind(self):
        """Pin the trailing-12-month underperformance phrase."""
        assert display(SignalName.COHORT_12M_BEHIND) == (
            "behind category peers over the trailing 12 months"
        )

    def test_cohort_3y_also_behind(self):
        """Pin the sustained (3Y) underperformance phrase."""
        assert display(SignalName.COHORT_3Y_ALSO_BEHIND) == (
            "also behind category peers over three years"
        )

    def test_nav_trailing_return(self):
        """Pin the trailing-return NAV phrase."""
        assert display(SignalName.NAV_TRAILING_RETURN) == (
            "trailing return computed from NAV history"
        )

    def test_nav_volatility_drawdown(self):
        """Pin the volatility/drawdown NAV phrase."""
        assert display(SignalName.NAV_VOLATILITY_DRAWDOWN) == (
            "volatility/drawdown computed from NAV history"
        )


# ---------------------------------------------------------------------------
# 3. Producer conformance — cohort paths
# ---------------------------------------------------------------------------

_BENCH = CohortBenchmark(
    "Large Cap",
    median_return_1y=10.0,
    median_return_3y=30.0,
    median_max_drawdown=15.0,
    n_peers=20,
)
_THIN_BENCH = CohortBenchmark(
    "Sectoral",
    median_return_1y=None,
    median_return_3y=None,
    median_max_drawdown=None,
    n_peers=3,
)


def _assert_canonical(signals: list[str], label: str = "") -> None:
    """Assert every string in ``signals`` is in CANONICAL_SIGNAL_PHRASES."""
    bad = [s for s in signals if s not in CANONICAL_SIGNAL_PHRASES]
    assert not bad, f"{label}: non-canonical signal strings found: {bad!r}"


def test_outperformer_signals_are_canonical():
    """Outperformer contributing/contradicting strings are all canonical."""
    cr = compare_to_cohort((18.0, 45.0, 9.0), _BENCH)
    _assert_canonical(cr.contributing, "outperformer contributing")
    _assert_canonical(cr.contradicting, "outperformer contradicting")


def test_underperformer_signals_are_canonical():
    """Underperformer contributing/contradicting strings are all canonical."""
    cr = compare_to_cohort((4.0, 20.0, 25.0), _BENCH)
    _assert_canonical(cr.contributing, "underperformer contributing")
    _assert_canonical(cr.contradicting, "underperformer contradicting")


def test_young_fund_signals_are_canonical():
    """Young-fund (1Y ahead, no 3Y) signals are canonical and short-track phrase present."""
    cr = compare_to_cohort((25.0, None, 8.0), _BENCH)
    _assert_canonical(cr.contributing, "young-fund contributing")
    _assert_canonical(cr.contradicting, "young-fund contradicting")
    assert display(SignalName.COHORT_1Y_AHEAD_SHORT_TRACK) in cr.contributing


def test_thin_benchmark_signals_are_canonical():
    """Thin-cohort path emits the canonical unavailability phrase."""
    cr = compare_to_cohort((30.0, 50.0, 5.0), _THIN_BENCH)
    _assert_canonical(cr.contributing, "thin-benchmark contributing")
    _assert_canonical(cr.contradicting, "thin-benchmark contradicting")
    assert display(SignalName.COHORT_THIN_BENCHMARK) in cr.contributing


def test_no_benchmark_yields_empty_signals():
    """No benchmark supplied → both lists empty."""
    cr = compare_to_cohort((50.0, 80.0, 5.0), None)
    assert not cr.contributing and not cr.contradicting


def test_matching_fund_yields_no_signals():
    """Inside the margin band → no flags, no signals."""
    cr = compare_to_cohort((10.5, 29.5, 16.0), _BENCH)
    assert not cr.contributing and not cr.contradicting


def test_drawdown_only_signal_is_canonical():
    """Shallower drawdown + matching returns emits only the drawdown phrase."""
    cr = compare_to_cohort((10.5, 29.5, 9.0), _BENCH)
    _assert_canonical(cr.contributing, "drawdown-only contributing")
    assert display(SignalName.COHORT_DRAWDOWN_CONTAINED) in cr.contributing


def test_sustained_underperformance_signals_are_canonical():
    """Sustained (1Y + 3Y) underperformance emits both canonical contradicting phrases."""
    cr = compare_to_cohort((3.0, 20.0, 25.0), _BENCH)
    _assert_canonical(cr.contradicting, "sustained underperformance contradicting")
    assert display(SignalName.COHORT_12M_BEHIND) in cr.contradicting
    assert display(SignalName.COHORT_3Y_ALSO_BEHIND) in cr.contradicting


# ---------------------------------------------------------------------------
# 4. signals.py NAV-producer conformance
# ---------------------------------------------------------------------------

_AS_OF = datetime.date(2026, 6, 6)


def _monthly_pts(*, months: int) -> list[tuple[datetime.date, float]]:
    """Build a monthly NAV series of ``months`` points ending at ``_AS_OF``."""
    pts = []
    nav = 100.0
    for i in range(months):
        d = _AS_OF - datetime.timedelta(days=30 * (months - 1 - i))
        pts.append((d, round(nav, 4)))
        nav *= 1.005
    return pts


def test_nav_contributing_signals_are_canonical():
    """NAV-derived signals are canonical; both phrases present for a healthy series."""
    pts = _monthly_pts(months=14)
    sig = compute_fund_signals("INF_TEST", pts, as_of=_AS_OF)
    _assert_canonical(sig.contributing, "NAV signals contributing")
    _assert_canonical(sig.contradicting, "NAV signals contradicting")
    assert display(SignalName.NAV_TRAILING_RETURN) in sig.contributing
    assert display(SignalName.NAV_VOLATILITY_DRAWDOWN) in sig.contributing


def test_thin_series_yields_no_signals():
    """Too-short NAV series → no contributing or contradicting signals."""
    sig = compute_fund_signals("INF_THIN", [(datetime.date(2026, 6, 1), 100.0)], as_of=_AS_OF)
    assert not sig.contributing and not sig.contradicting


def test_compute_with_category_relative_signals_are_canonical():
    """Signals merged from a CategoryRelative through compute_fund_signals are canonical."""
    pts = _monthly_pts(months=14)
    cr = compare_to_cohort((18.0, 45.0, 9.0), _BENCH)
    sig = compute_fund_signals("INF_CR", pts, as_of=_AS_OF, category_relative=cr)
    _assert_canonical(sig.contributing, "full-path contributing")
    _assert_canonical(sig.contradicting, "full-path contradicting")
