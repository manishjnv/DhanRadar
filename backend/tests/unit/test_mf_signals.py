"""
Unit tests for MF NAV → FundSignals (Phase 5, B29) — no DB/Redis/network.

Covers the B29 acceptance for the scoring seam:
  * happy path  — a healthy NAV series populates the momentum + risk axes (and
    leaves the fundamentals-backed axes None → partial coverage).
  * critical guard — too few NAV points → all axes None (engine refuses, which is
    the honest insufficient_data fail-safe).
  * end-to-end — a seeded NAV series scores a REAL label (not insufficient_data)
    through the published engine interface (the core B29 goal).

asyncio_mode = "auto" (pyproject.toml) — async tests need no decorator.
"""

from __future__ import annotations

import datetime

from dhanradar.mf.scoring_bridge import score_fund
from dhanradar.mf.signals import compute_fund_signals
from dhanradar.scoring.engine import RatingEngine, VerbLabel
from dhanradar.scoring.engine.schemas import ConfidenceBand


# --- fakes (avoid real Redis; mirror test_scoring_engine.py) -----------------
class _FakeHystStore:
    def __init__(self) -> None:
        self.d: dict = {}

    async def get(self, key):
        return self.d.get(key)

    async def set(self, key, state):
        self.d[key] = state


class _FakeResultStore:
    def __init__(self) -> None:
        self.d: dict = {}

    async def set(self, key, value, ex=None):
        self.d[key] = value


def _engine() -> RatingEngine:
    return RatingEngine(
        hysteresis_store=_FakeHystStore(),
        result_store=_FakeResultStore(),
    )


def _monthly_series(
    *, start_nav: float, monthly_growth_pct: float, months: int, end: datetime.date
) -> list[tuple[datetime.date, float]]:
    """Build a monthly NAV series of ``months`` points ENDING at ``end``."""
    pts: list[tuple[datetime.date, float]] = []
    nav = start_nav
    # Walk backwards so the last point lands exactly on ``end``.
    for i in range(months):
        d = end - datetime.timedelta(days=30 * (months - 1 - i))
        pts.append((d, round(nav, 4)))
        nav *= 1.0 + monthly_growth_pct / 100.0
    return pts


_AS_OF = datetime.date(2026, 6, 6)


# --- happy path --------------------------------------------------------------
def test_healthy_series_populates_momentum_and_risk_only():
    pts = _monthly_series(start_nav=100.0, monthly_growth_pct=1.5, months=14, end=_AS_OF)
    sig = compute_fund_signals("INF_HEALTHY", pts, as_of=_AS_OF)

    assert sig.isin == "INF_HEALTHY"
    # NAV-derived axes are present...
    assert sig.momentum is not None and sig.momentum > 50.0  # steadily rising → bullish momentum
    assert sig.risk is not None
    # ...fundamentals-backed axes are honestly absent (partial coverage).
    assert sig.quality is None and sig.valuation is None and sig.trend is None
    # Latest point is recent vs as_of → fully fresh, not stale.
    assert sig.freshness == 1.0 and sig.stale is False
    assert sig.liquid is True
    # No category-relative red flags asserted from NAV alone.
    assert sig.underperform_12m is False and sig.structural_concern is False


def test_stale_series_is_flagged_and_freshness_reduced():
    old_end = datetime.date(2026, 1, 1)  # > 30 days before as_of
    pts = _monthly_series(start_nav=100.0, monthly_growth_pct=1.0, months=10, end=old_end)
    sig = compute_fund_signals("INF_STALE", pts, as_of=_AS_OF)
    assert sig.stale is True and sig.freshness < 1.0


# --- critical guard ----------------------------------------------------------
def test_too_few_points_yields_no_axes():
    pts = [
        (datetime.date(2026, 5, 1), 100.0),
        (datetime.date(2026, 6, 1), 101.0),
    ]  # 2 points < _MIN_POINTS
    sig = compute_fund_signals("INF_THIN", pts, as_of=_AS_OF)
    assert sig.momentum is None and sig.risk is None
    assert sig.quality is None and sig.valuation is None and sig.trend is None


def test_empty_series_yields_no_axes():
    sig = compute_fund_signals("INF_EMPTY", [], as_of=_AS_OF)
    assert all(getattr(sig, ax) is None for ax in ("quality", "valuation", "momentum", "trend", "risk"))


# --- end-to-end: seeded NAV → REAL label (the B29 acceptance) ----------------
async def test_seeded_series_scores_a_real_label_not_insufficient_data():
    pts = _monthly_series(start_nav=100.0, monthly_growth_pct=1.5, months=14, end=_AS_OF)
    sig = compute_fund_signals("INF_REAL", pts, as_of=_AS_OF)

    result = await score_fund(_engine(), sig)

    # The whole point of B29: a fund with NAV history gets a REAL label.
    assert result.verb_label != VerbLabel.insufficient_data
    assert result.verb_label in {
        VerbLabel.in_form, VerbLabel.on_track, VerbLabel.off_track, VerbLabel.out_of_form,
    }
    assert result.confidence_band != ConfidenceBand.insufficient_data
    # NAV-only coverage is honestly capped at medium (fundamentals absent).
    assert result.confidence_band in {ConfidenceBand.medium, ConfidenceBand.low}
    assert "partial_coverage" in result.flags
    # A numeric IS computed server-side (never serialized to a client elsewhere).
    assert result.unified_score is not None


async def test_thin_series_scores_insufficient_data():
    """The honest fail-safe still holds end-to-end: no history → refuse."""
    sig = compute_fund_signals("INF_THIN2", [(datetime.date(2026, 6, 1), 100.0)], as_of=_AS_OF)
    result = await score_fund(_engine(), sig)
    assert result.verb_label == VerbLabel.insufficient_data
    assert result.unified_score is None  # no numeric exposed on refusal
