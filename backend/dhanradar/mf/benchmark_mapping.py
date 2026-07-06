"""
DhanRadar — index-fund → benchmark identity mapping (Block 0.7).

Pure module: given a scheme's ALREADY-CANONICALIZED SEBI category
(taxonomy.canonical_for's output) and its AMFI scheme name, derive the fund's
real per-fund benchmark — HIGH CONFIDENCE ONLY, index funds only. No DB /
network access — golden-set testable.

Governance (architecture plan §19, this repo's universal non-negotiable):
active (non-index) funds must NEVER get a ``benchmark_index`` value from a
guessed peer index. This module is gated to fire ONLY for the SEBI
"Other Scheme - Index Funds" leaf (taxonomy.py `_CANONICAL_LEAVES`) — every
other category returns None immediately, before the name-pattern table is
even consulted.

Registry alignment: the keys returned here (``"nifty50"``, ``"nifty100"``,
``"nifty500"``, ``"nifty_midcap_150"``) MUST exist in
``dhanradar.tasks.mf.BENCHMARK_REGISTRY``. This module deliberately does NOT
import that registry — ``tasks/mf.py`` already imports taxonomy helpers, so
importing the registry back from here would be a cycle. The caller
(``tasks/mf.py``'s ``_navrows_to_fund_upserts``) is responsible for
validating the returned key against its own registry before writing
``mf_funds.benchmark_index``. Only benchmarks the registry can actually
fetch/serve are ever mapped to.
"""

from __future__ import annotations

import re

#: The one SEBI taxonomy leaf this module ever fires for (taxonomy.py
#: `_CANONICAL_LEAVES` — "Other Scheme - Index Funds"). Any other
#: sebi_category → None, no exceptions.
_INDEX_FUND_CATEGORY = "Other Scheme - Index Funds"

#: Qualifier words that mean the scheme tracks a DERIVATIVE/variant index
#: (equal-weight, factor, ESG, …) that shares a headline number (e.g. "50")
#: with a plain-vanilla index but is NOT the same benchmark series — e.g.
#: "Nifty 50 Equal Weight Index Fund" tracks a different index than the
#: market-cap-weighted Nifty 50 in BENCHMARK_REGISTRY. Presence of any of
#: these forces None (ambiguous — never guess), even after a name-pattern
#: below would otherwise match.
_AMBIGUOUS_QUALIFIERS: tuple[str, ...] = (
    "equal weight",
    "esg",
    "quality",
    "value 20",
    "momentum",
    "alpha",
    "low volatility",
    "smart beta",
    "next",  # e.g. "Nifty Next 50" — a different, non-registry index
)

#: (name-pattern substring, BENCHMARK_REGISTRY key) — checked IN ORDER, first
#: match wins. Longer/more-specific index names are listed BEFORE their
#: shorter substrings: "nifty 500" before "nifty 50" — after normalization
#: "nifty 500" literally CONTAINS "nifty 50" as a substring (same leading 8
#: chars), so checking the longer name first is what prevents a Nifty 500
#: fund from being mis-mapped to nifty50. Only the 4 benchmarks with a
#: working BENCHMARK_REGISTRY entry are listed — Nifty Smallcap 250 (no
#: working Yahoo series, see tasks/mf.py registry comment) and every other
#: index are deliberately absent → None (never guessed).
_NAME_PATTERNS: tuple[tuple[str, str], ...] = (
    ("nifty midcap 150", "nifty_midcap_150"),
    ("nifty 500", "nifty500"),
    ("nifty 100", "nifty100"),
    ("nifty 50", "nifty50"),
)

#: Inserts a space at a letter→digit boundary so "Nifty50"/"MidCap150" (no
#: space before the number) normalize the same as "Nifty 50"/"Mid Cap 150".
_LETTER_DIGIT_BOUNDARY = re.compile(r"(?<=[a-z])(?=\d)")


def _normalize_for_match(scheme_name: str) -> str:
    """Lowercase + hyphen→space + letter/digit-boundary space + collapsed
    whitespace, so 'Nifty50', 'Nifty-50', and 'Nifty 50' all normalize to the
    same 'nifty 50' token before matching."""
    s = scheme_name.lower().replace("-", " ")
    s = _LETTER_DIGIT_BOUNDARY.sub(" ", s)
    return " ".join(s.split())


def map_index_fund_benchmark(scheme_name: str, sebi_category: str | None) -> str | None:
    """Return the BENCHMARK_REGISTRY key for an index fund's real benchmark, or
    None when unmapped (never guessed).

    Gated to fire ONLY for ``sebi_category == "Other Scheme - Index Funds"``
    (the canonical SEBI leaf, taxonomy.canonical_for's output — NOT the raw
    AMFI ``category`` string) — every other category returns None before the
    name-pattern table is even consulted, so an active fund can never be
    mistaken for an index fund by name alone.

    Within that gate, applies a small, high-confidence, ordered keyword table
    (see :data:`_NAME_PATTERNS`) — an ambiguous or unrecognized index name
    (e.g. "Nifty Smallcap 250", "Nifty Next 50", an equal-weight/factor
    variant) returns None rather than guessing.
    """
    if sebi_category != _INDEX_FUND_CATEGORY:
        return None
    if not scheme_name:
        return None

    norm = _normalize_for_match(scheme_name)
    if any(qualifier in norm for qualifier in _AMBIGUOUS_QUALIFIERS):
        return None

    for pattern, key in _NAME_PATTERNS:
        if pattern in norm:
            return key
    return None
