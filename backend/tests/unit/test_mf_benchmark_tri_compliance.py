"""Compliance tripwire (Phase 4c pt3/pt4, ADR-0033, binding) — raw TRI values must
NEVER reach the API/DOM. mf.mf_benchmark_tri is internal-compute only; the
router/schemas files that shape API responses must never mention it, and no response
payload may carry a `tri_value` key at any nesting depth.

Cheap grep-based guard, mirrors scripts/ci_guards.py's style (a plain substring/regex
scan of the source text) but lives as a unit test — it should fail loudly the moment
someone wires tri_value or the mf_benchmark_tri table into a client-facing surface.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from dhanradar.mf.comparison import rebase_series

_MF_DIR = Path(__file__).resolve().parents[2] / "dhanradar" / "mf"
_FORBIDDEN_TERMS = ("tri_value", "benchmark_tri")


def _read(name: str) -> str:
    return (_MF_DIR / name).read_text(encoding="utf-8")


def test_router_never_mentions_raw_tri():
    src = _read("router.py").lower()
    for term in _FORBIDDEN_TERMS:
        assert term not in src, (
            f"{term!r} found in router.py — TRI is internal-compute only (ADR-0033)"
        )


def test_schemas_never_mentions_raw_tri():
    src = _read("schemas.py").lower()
    for term in _FORBIDDEN_TERMS:
        assert term not in src, (
            f"{term!r} found in schemas.py — TRI is internal-compute only (ADR-0033)"
        )


def _walk_no_forbidden_keys(obj: object, forbidden: tuple[str, ...]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert k not in forbidden, f"forbidden key {k!r} found in comparison response"
            _walk_no_forbidden_keys(v, forbidden)
    elif isinstance(obj, list):
        for item in obj:
            _walk_no_forbidden_keys(item, forbidden)


def test_fund_comparison_response_schema_has_no_tri_value_key():
    """`fund.comparison` (Phase 4c pt4) response shape — every value has already
    passed through `rebase_series` (base-100 ratio), so no raw TRI/index level, and
    no `tri_value` key, can appear at any nesting depth. Mirrors the exact dict shape
    `dhanradar.mf.fund_read.get_fund_comparison` returns.
    """
    d0, d1 = date(2026, 1, 1), date(2026, 1, 2)
    response = {
        "window": "1y",
        "anchor_date": d0.isoformat(),
        "series": {
            "fund": rebase_series([(d1, 101.0)], d0, 100.0),
            "benchmark": {
                "points": rebase_series([(d1, 1010.0)], d0, 1000.0),
                "label": "Nifty 50 TRI",
                "is_fallback": False,
            },
            "category": {"points": None, "reason": "category average unavailable — cohort too thin"},
        },
        "disclosure": "Educational analysis only — not investment advice.",
        "not_advice": "NOT_ADVICE",
    }
    _walk_no_forbidden_keys(response, _FORBIDDEN_TERMS)
