"""Unit tests for the Compliance Audit service primitives (B26).

Pure unit tests — no Postgres, no Redis. Runs with the env-var stubs that
conftest.py injects before any dhanradar import (POSTGRES_PASSWORD, JWT_*).

Covered:
  * content_hash — deterministic; key-order-independent; distinct payloads diverge.
  * record_served_label(recommendation_type="buy_sell") — returns False BEFORE any DB
    access. Because no dhanradar.db engine is monkeypatched, any attempt to open a
    session would raise; the function must return False instead.
"""

from __future__ import annotations

from dhanradar.compliance.service import content_hash, record_served_label


# ---------------------------------------------------------------------------
# content_hash — deterministic + key-order-independent + distinct payloads ≠
# ---------------------------------------------------------------------------


def test_content_hash_deterministic():
    """Same dict produces the same hash on repeated calls."""
    payload = {"surface": "mf_report", "label": "on_track", "model": "v1",
               "disclaimer_version": "2026-06-06.v1", "identifier": "INF0001",
               "recommendation_type": "educational_label"}
    assert content_hash(payload) == content_hash(payload)


def test_content_hash_key_order_independent():
    """Hash is identical regardless of key-insertion order."""
    a = {"surface": "mf_report", "label": "on_track", "model": "v1",
         "disclaimer_version": "2026-06-06.v1"}
    # Build the same dict with keys in reverse order.
    b = {k: a[k] for k in reversed(list(a))}
    assert content_hash(a) == content_hash(b)


def test_content_hash_different_payloads_differ():
    """Different payloads produce different hashes."""
    base = {"surface": "mf_report", "label": "on_track", "model": "v1",
            "disclaimer_version": "2026-06-06.v1"}
    other = {**base, "label": "off_track"}
    assert content_hash(base) != content_hash(other)


def test_content_hash_returns_hex_string():
    """Output is a 64-char lowercase hex string (SHA-256)."""
    h = content_hash({"x": 1})
    assert isinstance(h, str)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# record_served_label — buy_sell is rejected BEFORE any DB access
# ---------------------------------------------------------------------------


async def test_record_served_label_buy_sell_returns_false_no_db():
    """recommendation_type='buy_sell' must return False immediately.

    No DB engine is monkeypatched; if the function tried to open a session it
    would raise (import-time or connection error), not return False. The test
    asserts the function returns False cleanly — proving it bails before the
    DB path.
    """
    result = await record_served_label(
        recommendation_type="buy_sell",
        surface="x",
        label="on_track",
        model="v1",
        disclaimer_version="2026-06-06.v1",
    )
    assert result is False


async def test_record_served_label_buy_sell_no_write_on_retry():
    """Multiple buy_sell calls all return False — the guard is unconditional."""
    for _ in range(3):
        result = await record_served_label(
            recommendation_type="buy_sell",
            surface="mf_report",
            label="in_form",
            model="v2",
            disclaimer_version="2026-06-06.v1",
        )
        assert result is False
