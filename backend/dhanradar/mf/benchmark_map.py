"""
DhanRadar — free-text AMFI benchmark name -> canonical TRI index key (Phase 4c pt3).

Pure module: no DB / network / Celery imports — golden-set testable, same pattern as
`dhanradar.mf.category_series` / `dhanradar.mf.benchmark_mapping`.

Why this exists (honest-fallback rule, MF_MASTER_DB_IMPROVEMENT_PLAN.md "Phase 4c"):
AMFI's per-scheme `benchmark_index` disclosure is free text — "Nifty 500 TRI",
"NIFTY Banking & PSU Debt Index A-II", "Nifty Midcap150 TRI", etc. New strings arrive
with every AMFI file, so mapping them to a series we actually fetch (`mf.mf_benchmark_tri`)
must be DATA (`mf.mf_benchmark_map`), not a code deploy. `candidate_index_key()` is the
seed logic: it returns one of the 4 canonical keys ONLY on a confident match — every other
string (debt/hybrid benchmarks, an index we don't carry, an ambiguous factor/ESG variant)
returns None rather than guessing. Unmapped strings surface on the admin coverage page;
the UI falls back honestly ("vs Nifty 50 (broad market — not this scheme's benchmark)").

Distinct from `dhanradar.mf.benchmark_mapping` (Block 0.7): that module derives an INDEX
FUND's own benchmark from its SCHEME NAME (gated to the "Other Scheme - Index Funds" SEBI
leaf, feeding the price-index `mf_benchmark_daily`/`BENCHMARK_REGISTRY` machinery). This
module maps the AMFI-DISCLOSED BENCHMARK STRING (any scheme, any category) to a TRI series
key — a different input, a different (internal-compute-only, ADR-0033) output table, no
shared registry.

Canonical index keys are the single source of truth for both consumers: the seed task
(`dhanradar.tasks.mf.benchmark_map_seed`, writes `mf.mf_benchmark_map.index_key`) and the
TRI fetch task (`dhanradar.tasks.mf.benchmark_tri_fetch`, writes `mf.mf_benchmark_tri.index_key`).
"""

from __future__ import annotations

import re

#: The only 4 TRI series DhanRadar fetches (niftyindices.com — see tasks/mf.py
#: `benchmark_tri_fetch`). Debt/hybrid/other equity indices have no CRISIL-licensed
#: series available (MF_MASTER_DB_IMPROVEMENT_PLAN.md "Phase 4c") — the category-median
#: line is the primary comparison there. Never add a key here without a matching fetcher
#: entry in tasks/mf.py's `_TRI_NIFTYINDICES_NAME`.
NIFTY50_TRI = "nifty50_tri"
NIFTY_MIDCAP150_TRI = "nifty_midcap150_tri"
NIFTY_SMALLCAP250_TRI = "nifty_smallcap250_tri"
NIFTY500_TRI = "nifty500_tri"

CANONICAL_INDEX_KEYS: tuple[str, ...] = (
    NIFTY50_TRI,
    NIFTY_MIDCAP150_TRI,
    NIFTY_SMALLCAP250_TRI,
    NIFTY500_TRI,
)

#: Qualifier words meaning the benchmark tracks a DERIVATIVE/variant index that shares a
#: headline number with a plain-vanilla one but is NOT the same series (e.g. "Nifty 50
#: Equal Weight TRI" is not our `nifty50_tri`) — presence forces None, never guessed.
#: Mirrors `dhanradar.mf.benchmark_mapping._AMBIGUOUS_QUALIFIERS`.
_AMBIGUOUS_QUALIFIERS: tuple[str, ...] = (
    "equal weight",
    "esg",
    "quality",
    "value",
    "momentum",
    "alpha",
    "low volatility",
    "smart beta",
    "next",
    "shariah",
    "total market",
    "high beta",
    "dividend opportunities",
)

#: (normalized substring, canonical key) — checked IN ORDER. Longer/more-specific index
#: names are listed before their shorter substrings: "nifty midcap 150"/"nifty smallcap
#: 250" before "nifty 500"/"nifty 50" — and "nifty 500" before "nifty 50", since "nifty
#: 500" literally contains "nifty 50" as a leading substring after normalization.
_NAME_PATTERNS: tuple[tuple[str, str], ...] = (
    ("nifty midcap 150", NIFTY_MIDCAP150_TRI),
    ("nifty mid cap 150", NIFTY_MIDCAP150_TRI),
    ("nifty smallcap 250", NIFTY_SMALLCAP250_TRI),
    ("nifty small cap 250", NIFTY_SMALLCAP250_TRI),
    ("nifty 500", NIFTY500_TRI),
    ("nifty 50", NIFTY50_TRI),
)

_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_INDEX_RE = re.compile(r"\bindex\.?$")
_TOTAL_RETURN_RE = re.compile(r"total returns? index")
_PAREN_TRI_RE = re.compile(r"\(\s*tri\s*\)")
# letter/digit boundary both ways, so "Midcap150"/"150TRI" normalize the same as
# "Midcap 150"/"150 TRI" (mirrors benchmark_mapping._LETTER_DIGIT_BOUNDARY).
_LETTER_DIGIT_RE = re.compile(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])")
_HYPHEN_RE = re.compile(r"-")


def normalize_benchmark_name(raw: str) -> str:
    """Trim, collapse whitespace, casefold, unify TRI phrasing, strip a trailing
    standalone "index" word.

    "Nifty 500 TRI" / "nifty500tri" / "NIFTY 500 Total Return Index" / "Nifty 500 (TRI)"
    all normalize to "nifty 500 tri". "NIFTY Banking & PSU Debt Index A-II" keeps its
    "index" (not trailing — followed by "A-II"), so it stays clearly distinguishable.
    """
    if not raw:
        return ""
    s = _HYPHEN_RE.sub(" ", raw.strip()).casefold()
    s = _PAREN_TRI_RE.sub(" tri ", s)
    s = _TOTAL_RETURN_RE.sub(" tri ", s)
    s = _LETTER_DIGIT_RE.sub(" ", s)
    s = _WHITESPACE_RE.sub(" ", s).strip()
    s = _TRAILING_INDEX_RE.sub("", s).strip()
    return _WHITESPACE_RE.sub(" ", s).strip()


def candidate_index_key(raw: str) -> str | None:
    """Return a canonical TRI index key for `raw`, or None (never guessed).

    Confident-match only: requires the normalized string to (1) contain a standalone
    "tri" token — a scheme's benchmark disclosure not explicitly naming TRI/Total Return
    Index is not assumed to mean the TRI series even though SEBI mandates TRI benchmarking
    (the raw string itself doesn't confirm it), (2) carry none of the ambiguous-variant
    qualifiers, and (3) match exactly one of the 4 canonical index name patterns.
    """
    if not raw:
        return None
    norm = normalize_benchmark_name(raw)
    if not norm:
        return None
    tokens = norm.split()
    if "tri" not in tokens:
        return None
    if any(qualifier in norm for qualifier in _AMBIGUOUS_QUALIFIERS):
        return None
    for pattern, key in _NAME_PATTERNS:
        if pattern in norm:
            return key
    return None
