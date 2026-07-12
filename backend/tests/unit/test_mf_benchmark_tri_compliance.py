"""Compliance tripwire (Phase 4c pt3, ADR-0033, binding) — raw TRI values must NEVER
reach the API/DOM. mf.mf_benchmark_tri is internal-compute only; the router/schemas
files that shape API responses must never mention it.

Cheap grep-based guard, mirrors scripts/ci_guards.py's style (a plain substring/regex
scan of the source text) but lives as a unit test — it should fail loudly the moment
someone wires tri_value or the mf_benchmark_tri table into a client-facing surface.
"""

from __future__ import annotations

from pathlib import Path

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
