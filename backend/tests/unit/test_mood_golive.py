"""
Unit tests for Mood Compass go-live gaps (B35):
  GAP c — unavailable_public() structured 200
  GAP d — _labelize / human factor labels
  GAP g — _compute_trend (non-numeric trend label)
  GAP b — get_embed_html (no-numeric embed widget)
  GAP a — signals.py normalization helpers

All tests are UNIT-level: no DB, no Redis, no network.
DB-dependent helpers (_compute_trend, get_latest, get_embed_html) are tested
with lightweight fake DB objects so no integration infrastructure is required.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dhanradar.mood.compute import WEIGHTS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(mood_score: float, snapshot_date: date | None = None) -> MagicMock:
    """Build a fake MarketMood ORM row with the fields service.py reads."""
    row = MagicMock()
    row.mood_score = mood_score
    row.snapshot_date = snapshot_date or date.today()
    row.regime = "neutral"
    row.confidence_band = "medium"
    row.data_quality = "ok"
    row.contributing_factors = ["nifty_trend", "market_breadth"]
    row.contradicting_factors = ["india_vix"]
    row.ai_commentary = None
    return row


class _FakeScalars:
    """Mimics the result of await db.scalars(...)."""

    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    """Minimal async DB session double for _compute_trend / get_latest tests."""

    def __init__(self, rows):
        self._rows = rows

    async def scalar(self, _stmt):
        return self._rows[0] if self._rows else None

    async def scalars(self, _stmt):
        return _FakeScalars(self._rows)


# ---------------------------------------------------------------------------
# 1. compute_and_store with partial inputs → non-None MoodResult
# ---------------------------------------------------------------------------


async def test_compute_and_store_partial_inputs_returns_result():
    """compute_and_store with 4 non-None inputs must return a non-None MoodResult
    with a real regime and confidence_band (unit: _persist/_cache_latest/emit_published
    are nopped via monkeypatch)."""
    from dhanradar.mood import service

    subset = {k: None for k in WEIGHTS}
    subset["nifty_trend"] = 0.7
    subset["india_vix"] = 0.6
    subset["market_breadth"] = 0.55
    subset["put_call_ratio"] = 0.5

    with (
        patch.object(service, "_persist", new=AsyncMock()),
        patch.object(service, "_cache_latest", new=AsyncMock()),
        patch.object(service, "emit_published", new=AsyncMock()),
    ):
        result = await service.compute_and_store(
            snapshot_date=date.today(),
            snapshot_time=datetime.now(UTC),
            fetch=lambda: subset,
        )

    assert result is not None, "Expected a MoodResult, got None"
    assert result.regime in {
        "extreme_fear", "fear", "neutral", "greed", "extreme_greed", "insufficient_data"
    }, f"Unexpected regime: {result.regime!r}"
    assert result.confidence_band in {"high", "medium", "low", "insufficient_data"}, (
        f"Unexpected confidence_band: {result.confidence_band!r}"
    )


# ---------------------------------------------------------------------------
# 2. unavailable_public — structured 200 response (GAP c)
# ---------------------------------------------------------------------------


def test_unavailable_public_regime():
    from dhanradar.mood.service import unavailable_public

    pub = unavailable_public()
    assert pub.regime == "data_unavailable"
    assert pub.confidence_band == "insufficient_data"
    assert pub.data_quality == "unavailable"
    assert pub.disclosure, "disclosure must be non-empty"
    assert pub.not_advice, "not_advice must be non-empty"
    assert pub.disclaimer_version, "disclaimer_version must be non-empty"
    assert pub.contributing_factors == []
    assert pub.contradicting_factors == []
    assert pub.commentary is None
    assert pub.trend is None


def test_unavailable_public_no_numerics():
    """unavailable_public must not contain any numeric mood_score/confidence_score."""
    from dhanradar.mood.service import unavailable_public

    pub = unavailable_public()
    pub_dict = pub.model_dump()
    assert "mood_score" not in pub_dict, "mood_score must not appear in public response"
    assert "confidence_score" not in pub_dict, "confidence_score must not appear in public response"


def test_why_today_unavailable_structured_200():
    """/why-today must return a structured data_unavailable (not 404) when no
    snapshot exists — consistent with /mood (Phase-7 Product finding fix). No
    numeric leak; disclosure bundle present."""
    from dhanradar.mood.service import why_today_unavailable

    why = why_today_unavailable()
    assert why.regime == "data_unavailable"
    assert why.commentary is None
    assert why.contributing_factors == [] and why.contradicting_factors == []
    assert why.disclosure and why.not_advice and why.disclaimer_version
    d = why.model_dump()
    assert "mood_score" not in d and "confidence_score" not in d


# ---------------------------------------------------------------------------
# 3. _labelize — human-readable factor labels (GAP d)
# ---------------------------------------------------------------------------


def test_labelize_known_keys():
    from dhanradar.mood.service import _labelize

    result = _labelize(["put_call_ratio", "india_vix"])
    assert result == ["Put-Call Ratio", "India VIX"], f"Got: {result}"


def test_labelize_unknown_key_passthrough():
    from dhanradar.mood.service import _labelize

    result = _labelize(["put_call_ratio", "unknown_signal"])
    assert result[0] == "Put-Call Ratio"
    assert result[1] == "unknown_signal", "Unknown key must pass through unchanged"


def test_labelize_all_weights_keys_covered():
    """Every WEIGHTS key must have a human label in _FACTOR_LABELS."""
    from dhanradar.mood.service import _FACTOR_LABELS

    missing = [k for k in WEIGHTS if k not in _FACTOR_LABELS]
    assert not missing, f"Missing labels for: {missing}"


def test_labelize_empty_list():
    from dhanradar.mood.service import _labelize

    assert _labelize([]) == []


# ---------------------------------------------------------------------------
# 4. _compute_trend — non-numeric trend label (GAP g)
# ---------------------------------------------------------------------------


async def test_compute_trend_improving():
    from dhanradar.mood.service import _compute_trend

    rows = [_make_row(70.0), _make_row(65.0)]  # latest first
    db = _FakeDb(rows)
    trend = await _compute_trend(db)
    assert trend == "improving", f"Expected 'improving', got {trend!r}"


async def test_compute_trend_deteriorating():
    from dhanradar.mood.service import _compute_trend

    rows = [_make_row(40.0), _make_row(45.0)]  # latest < prior by >2
    db = _FakeDb(rows)
    trend = await _compute_trend(db)
    assert trend == "deteriorating", f"Expected 'deteriorating', got {trend!r}"


async def test_compute_trend_stable():
    from dhanradar.mood.service import _compute_trend

    rows = [_make_row(51.0), _make_row(50.0)]  # diff = 1.0, within ±2
    db = _FakeDb(rows)
    trend = await _compute_trend(db)
    assert trend == "stable", f"Expected 'stable', got {trend!r}"


async def test_compute_trend_none_when_single_row():
    from dhanradar.mood.service import _compute_trend

    db = _FakeDb([_make_row(55.0)])
    trend = await _compute_trend(db)
    assert trend is None, f"Expected None for <2 rows, got {trend!r}"


async def test_compute_trend_none_when_no_rows():
    from dhanradar.mood.service import _compute_trend

    db = _FakeDb([])
    trend = await _compute_trend(db)
    assert trend is None, f"Expected None for empty table, got {trend!r}"


async def test_compute_trend_boundary_exactly_plus_two():
    """diff = +2.0 is NOT > 2.0 → stable (strict boundary)."""
    from dhanradar.mood.service import _compute_trend

    rows = [_make_row(52.0), _make_row(50.0)]
    db = _FakeDb(rows)
    assert await _compute_trend(db) == "stable"


async def test_compute_trend_boundary_just_above_plus_two():
    """diff = +2.01 → improving."""
    from dhanradar.mood.service import _compute_trend

    rows = [_make_row(52.01), _make_row(50.0)]
    db = _FakeDb(rows)
    assert await _compute_trend(db) == "improving"


# ---------------------------------------------------------------------------
# 5. get_embed_html — no-numeric embed widget (GAP b)
# ---------------------------------------------------------------------------


async def test_get_embed_html_no_numerics():
    """The embed HTML must not contain numeric mood_score / confidence_score."""
    from dhanradar.mood import service

    rows = [_make_row(72.5)]
    db = _FakeDb(rows)

    # Patch Redis so the embed is generated fresh (cache miss).
    fake_redis = AsyncMock()
    fake_redis.get = AsyncMock(return_value=None)
    fake_redis.set = AsyncMock()

    with patch("dhanradar.redis_client.get_redis", return_value=fake_redis):
        html = await service.get_embed_html(db)

    assert isinstance(html, str)
    assert "mood_score" not in html, "mood_score must not appear in embed HTML"
    assert "confidence_score" not in html, "confidence_score must not appear in embed HTML"

    # Must not contain a bare 0–100 number that would reveal the score
    # (72.5 is the row's mood_score — must not appear in output)
    assert "72.5" not in html, "raw mood_score value must not appear in embed HTML"


async def test_get_embed_html_contains_required_text():
    """The embed HTML must contain regime display, NOT_ADVICE and disclosure."""
    from dhanradar.mood import service

    rows = [_make_row(72.5)]
    db = _FakeDb(rows)

    fake_redis = AsyncMock()
    fake_redis.get = AsyncMock(return_value=None)
    fake_redis.set = AsyncMock()

    with patch("dhanradar.redis_client.get_redis", return_value=fake_redis):
        html = await service.get_embed_html(db)

    # Regime is "neutral" on the fake row; humanized to "Neutral"
    assert "Neutral" in html, f"Expected regime 'Neutral' in embed, got snippet: {html[:300]}"
    assert "NOT_ADVICE" in html, "NOT_ADVICE must appear in embed"


async def test_get_embed_html_unavailable_when_no_rows():
    """With no DB rows, embed shows data_unavailable content (not a crash)."""
    from dhanradar.mood import service

    db = _FakeDb([])

    fake_redis = AsyncMock()
    fake_redis.get = AsyncMock(return_value=None)
    fake_redis.set = AsyncMock()

    with patch("dhanradar.redis_client.get_redis", return_value=fake_redis):
        html = await service.get_embed_html(db)

    assert isinstance(html, str)
    assert "Data Unavailable" in html or "data_unavailable" in html.lower(), (
        f"Expected data_unavailable in embed for empty DB, got: {html[:300]}"
    )


async def test_get_embed_html_cache_hit():
    """On a Redis cache hit the cached HTML is returned without a DB query."""
    from dhanradar.mood import service

    db = _FakeDb([])  # would cause data_unavailable if queried

    cached_html = "<html>cached</html>"
    fake_redis = AsyncMock()
    fake_redis.get = AsyncMock(return_value=cached_html)

    with patch("dhanradar.redis_client.get_redis", return_value=fake_redis):
        html = await service.get_embed_html(db)

    assert html == cached_html


# ---------------------------------------------------------------------------
# 6. signals.py — normalization unit tests (GAP a)
# ---------------------------------------------------------------------------


class TestNormNiftyTrend:
    def test_plus_three_clamps_to_one(self):
        from dhanradar.mood.signals import norm_nifty_trend
        assert norm_nifty_trend(3.0) == 1.0

    def test_minus_three_clamps_to_zero(self):
        from dhanradar.mood.signals import norm_nifty_trend
        assert norm_nifty_trend(-3.0) == 0.0

    def test_zero_is_half(self):
        from dhanradar.mood.signals import norm_nifty_trend
        assert abs(norm_nifty_trend(0.0) - 0.5) < 1e-9

    def test_beyond_plus_three_clamped(self):
        from dhanradar.mood.signals import norm_nifty_trend
        assert norm_nifty_trend(10.0) == 1.0

    def test_beyond_minus_three_clamped(self):
        from dhanradar.mood.signals import norm_nifty_trend
        assert norm_nifty_trend(-10.0) == 0.0


class TestNormIndiaVix:
    def test_high_vix_yields_low_value(self):
        """VIX = 30 (high fear) → 0.0"""
        from dhanradar.mood.signals import norm_india_vix
        assert norm_india_vix(30.0) == 0.0

    def test_low_vix_yields_high_value(self):
        """VIX = 10 (low fear) → 1.0"""
        from dhanradar.mood.signals import norm_india_vix
        assert norm_india_vix(10.0) == 1.0

    def test_mid_vix_is_half(self):
        from dhanradar.mood.signals import norm_india_vix
        assert abs(norm_india_vix(20.0) - 0.5) < 1e-9

    def test_very_high_vix_clamps_to_zero(self):
        from dhanradar.mood.signals import norm_india_vix
        assert norm_india_vix(80.0) == 0.0


class TestNormMarketBreadth:
    def test_all_advancing_is_one(self):
        from dhanradar.mood.signals import norm_market_breadth
        assert norm_market_breadth(1.0) == 1.0

    def test_all_declining_is_zero(self):
        from dhanradar.mood.signals import norm_market_breadth
        assert norm_market_breadth(0.0) == 0.0

    def test_half_is_half(self):
        from dhanradar.mood.signals import norm_market_breadth
        assert norm_market_breadth(0.5) == 0.5

    def test_clamps_above_one(self):
        from dhanradar.mood.signals import norm_market_breadth
        assert norm_market_breadth(1.5) == 1.0


class TestNormPutCallRatio:
    def test_high_pcr_yields_low_value(self):
        """PCR = 1.3 (high fear) → 0.0"""
        from dhanradar.mood.signals import norm_put_call_ratio
        assert norm_put_call_ratio(1.3) == 0.0

    def test_low_pcr_yields_high_value(self):
        """PCR = 0.7 (low fear) → 1.0"""
        from dhanradar.mood.signals import norm_put_call_ratio
        assert norm_put_call_ratio(0.7) == 1.0

    def test_mid_pcr_is_half(self):
        from dhanradar.mood.signals import norm_put_call_ratio
        assert abs(norm_put_call_ratio(1.0) - 0.5) < 1e-9

    def test_very_high_pcr_clamps_to_zero(self):
        from dhanradar.mood.signals import norm_put_call_ratio
        assert norm_put_call_ratio(3.0) == 0.0


# ---------------------------------------------------------------------------
# 7. fetch_mood_inputs — graceful degradation on adapter failure
# ---------------------------------------------------------------------------


async def test_fetch_mood_inputs_all_providers_failed():
    """AllProvidersFailedError → returns all-None dict (graceful degradation)."""
    from dhanradar.market_data.config import DataKind
    from dhanradar.market_data.exceptions import AllProvidersFailedError
    from dhanradar.mood.signals import fetch_mood_inputs

    class _FailAdapter:
        async def fetch(self, _request):
            raise AllProvidersFailedError(DataKind.MACRO_SIGNAL, [])

    inputs = await fetch_mood_inputs(_FailAdapter())
    assert set(inputs.keys()) == set(WEIGHTS.keys())
    assert all(v is None for v in inputs.values()), "All values must be None on provider failure"


async def test_fetch_mood_inputs_normalizes_signals():
    """A successful MacroSignalReceived event → correct normalised values in inputs dict."""
    from dhanradar.market_data.events import MacroSignalReceived
    from dhanradar.mood.signals import fetch_mood_inputs, norm_india_vix, norm_nifty_trend

    raw = {"nifty_trend": 1.5, "india_vix": 18.0, "market_breadth": 0.6, "put_call_ratio": 1.1}
    event = MacroSignalReceived(source="nse_macro", signals=raw, fetched_at="2026-06-08T00:00:00")

    class _OkAdapter:
        async def fetch(self, _request):
            return event

    inputs = await fetch_mood_inputs(_OkAdapter())

    assert inputs["nifty_trend"] == pytest.approx(norm_nifty_trend(1.5))
    assert inputs["india_vix"] == pytest.approx(norm_india_vix(18.0))
    assert inputs["market_breadth"] == pytest.approx(0.6)
    # Remaining 7 keys stay None
    for k in WEIGHTS:
        if k not in raw:
            assert inputs[k] is None, f"Expected None for {k!r}, got {inputs[k]}"
