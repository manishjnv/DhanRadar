"""
DhanRadar — free-text AMFI benchmark name -> canonical TRI index key (Phase 4c pt3).

Pure module: no DB / network / Celery imports — golden-set testable, same pattern as
`dhanradar.mf.category_series` / `dhanradar.mf.benchmark_mapping`.

Why this exists (honest-fallback rule, MF_MASTER_DB_IMPROVEMENT_PLAN.md "Phase 4c"):
AMFI's per-scheme `benchmark_index` disclosure is free text — "Nifty 500 TRI",
"NIFTY Banking & PSU Debt Index A-II", "Nifty Midcap150 TRI", etc. New strings arrive
with every AMFI file, so mapping them to a series we actually fetch (`mf.mf_benchmark_tri`)
must be DATA (`mf.mf_benchmark_map`), not a code deploy. `candidate_index_key()` is the
seed logic: a confident match means the normalized string is EXACTLY one of the known
spelling forms of a canonical index name — never a substring/containment match. Real AMFI
strings like "NIFTY 50 Hybrid Composite Debt 65:35 Index TRI" (the standard aggressive-
hybrid benchmark), "NIFTY500 Multicap 50:25:25 TRI", or "Nifty 50 Arbitrage TRI" CONTAIN
a canonical name but denote a DIFFERENT index, and no qualifier blacklist can enumerate
them all. Every other string (debt/hybrid benchmarks, an index we don't carry, a
factor/ESG/arbitrage variant) returns None rather than guessing. Unmapped strings surface
on the admin coverage page; the UI falls back honestly ("vs Nifty 50 (broad market — not
this scheme's benchmark)").

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

#: normalized string -> canonical key, EXACT EQUALITY only (post-normalization). Any
#: string that merely CONTAINS one of these forms ("nifty 50 hybrid composite debt 65:35
#: tri", "nifty 500 multicap 50:25:25 tri", "nifty 50 arbitrage tri", "nifty 50 equal
#: weight tri", …) is a DIFFERENT index and must fall through to None — exact equality is
#: the gate, so no qualifier blacklist is needed (a variant string can never equal a
#: canonical form). Every "tri" here is guaranteed by normalize_benchmark_name(), which
#: unifies "TRI" / "(TRI)" / "Total Return(s) Index" spellings.
_ALLOWED_FORMS: dict[str, str] = {
    "nifty 50 tri": NIFTY50_TRI,
    "nifty 500 tri": NIFTY500_TRI,
    "nifty midcap 150 tri": NIFTY_MIDCAP150_TRI,
    "nifty mid cap 150 tri": NIFTY_MIDCAP150_TRI,
    "nifty smallcap 250 tri": NIFTY_SMALLCAP250_TRI,
    "nifty small cap 250 tri": NIFTY_SMALLCAP250_TRI,
}

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

    Confident-match only: the normalized string must EQUAL one of the known spelling
    forms in `_ALLOWED_FORMS` exactly — never a substring/containment match (a string
    that merely contains a canonical name, e.g. "NIFTY 50 Hybrid Composite Debt 65:35
    Index TRI", denotes a different index). This also implies the TRI signal is
    explicit: a bare "Nifty 50" (no TRI/Total Return Index in the raw string) is not
    assumed to mean the TRI series and returns None.
    """
    if not raw:
        return None
    return _ALLOWED_FORMS.get(normalize_benchmark_name(raw))
