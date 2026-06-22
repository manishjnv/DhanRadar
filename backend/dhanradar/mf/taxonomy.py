"""
DhanRadar — MF category taxonomy validation + canonicalization (B66).

Source of truth:
  * SEBI circular SEBI/HO/IMD/DF3/CIR/P/2017/114 (October 6, 2017) — MF
    categorization and rationalization: defines the 36 permitted scheme
    categories across 5 class groups (Equity / Debt / Hybrid /
    Solution-Oriented / Other Scheme).
  * AMFI NAVAll.txt section headers — the live feed emits scheme-type strings
    that correspond (with minor presentation variations) to those 36 SEBI leaf
    categories plus a handful of bare-legacy strings predating the circular.

INVARIANT: this module NEVER mutates the raw ``category`` cohort key stored in
``mf_funds.category``.  It only classifies raw category strings and produces
the ``sebi_category`` canonical value.  The cohort scoring in
``mf/cohort.py`` groups peers by exact ``category`` string equality; touching
that column would silently regroup cohorts and corrupt category-relative labels.
All writes from this module go to ``mf_funds.sebi_category`` only.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Canonical SEBI leaf set (42 strings)
# ---------------------------------------------------------------------------
# Normalized form: single internal spaces, straight apostrophe (U+0027).
# "Equity Scheme - Sectoral/ Thematic" keeps the space after the slash — that
# is the canonical AMFI presentation of the SEBI sectoral/thematic category.
# "Other Scheme - Other ETFs" uses a single space between Other and ETFs.

_CANONICAL_LEAVES: frozenset[str] = frozenset(
    {
        # Equity — 12 leaves
        "Equity Scheme - Contra Fund",
        "Equity Scheme - Dividend Yield Fund",
        "Equity Scheme - ELSS",
        "Equity Scheme - Flexi Cap Fund",
        "Equity Scheme - Focused Fund",
        "Equity Scheme - Large & Mid Cap Fund",
        "Equity Scheme - Large Cap Fund",
        "Equity Scheme - Mid Cap Fund",
        "Equity Scheme - Multi Cap Fund",
        "Equity Scheme - Sectoral/ Thematic",
        "Equity Scheme - Small Cap Fund",
        "Equity Scheme - Value Fund",
        # Debt — 16 leaves
        "Debt Scheme - Banking and PSU Fund",
        "Debt Scheme - Corporate Bond Fund",
        "Debt Scheme - Credit Risk Fund",
        "Debt Scheme - Dynamic Bond",
        "Debt Scheme - Floater Fund",
        "Debt Scheme - Gilt Fund",
        "Debt Scheme - Gilt Fund with 10 year constant duration",
        "Debt Scheme - Liquid Fund",
        "Debt Scheme - Long Duration Fund",
        "Debt Scheme - Low Duration Fund",
        "Debt Scheme - Medium Duration Fund",
        "Debt Scheme - Medium to Long Duration Fund",
        "Debt Scheme - Money Market Fund",
        "Debt Scheme - Overnight Fund",
        "Debt Scheme - Short Duration Fund",
        "Debt Scheme - Ultra Short Duration Fund",
        # Hybrid — 7 leaves
        "Hybrid Scheme - Aggressive Hybrid Fund",
        "Hybrid Scheme - Arbitrage Fund",
        "Hybrid Scheme - Balanced Hybrid Fund",
        "Hybrid Scheme - Conservative Hybrid Fund",
        "Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage",
        "Hybrid Scheme - Equity Savings",
        "Hybrid Scheme - Multi Asset Allocation",
        # Solution Oriented — 2 leaves
        "Solution Oriented Scheme - Children's Fund",
        "Solution Oriented Scheme - Retirement Fund",
        # Other Scheme — 5 leaves
        "Other Scheme - FoF Domestic",
        "Other Scheme - FoF Overseas",
        "Other Scheme - Gold ETF",
        "Other Scheme - Index Funds",
        "Other Scheme - Other ETFs",
    }
)

# ---------------------------------------------------------------------------
# Legacy maps
# ---------------------------------------------------------------------------

# Unambiguous bare-header → canonical leaf.  Only strings that map to exactly
# one SEBI leaf are placed here; ambiguous ones go to _LEGACY_UNMAPPABLE.
_LEGACY_MAP: dict[str, str] = {
    "ELSS": "Equity Scheme - ELSS",
}

# Recognized old/ambiguous bare headers that we deliberately do NOT auto-map.
# "Gilt" is ambiguous between two SEBI Gilt leaves; "Growth" / "Income" /
# "Money Market" are pre-rationalization umbrella names with no single mapping.
_LEGACY_UNMAPPABLE: frozenset[str] = frozenset(
    {"Gilt", "Growth", "Income", "Money Market"}
)

# Pre-compiled pattern: any run of whitespace (tabs, double spaces, etc.)
_WS_RUN = re.compile(r"\s+")

# Curly apostrophes → straight apostrophe
_CURLY_APOSTROPHES = str.maketrans(
    {
        "’": "'",  # RIGHT SINGLE QUOTATION MARK  '
        "‘": "'",  # LEFT SINGLE QUOTATION MARK   '
    }
)


# ---------------------------------------------------------------------------
# Normalize
# ---------------------------------------------------------------------------


def normalize(raw: str | None) -> str | None:
    """Return a cleaned string or None.

    * None / blank / whitespace-only → None.
    * Strip leading and trailing whitespace.
    * Replace curly apostrophes (U+2018, U+2019) with straight ``'`` (U+0027).
    * Collapse any internal whitespace run (tabs, double spaces, etc.) to a
      single ASCII space.
    """
    if not isinstance(raw, str):
        # None — or any unexpected non-str type from an upstream parser regression.
        # canonical_for() runs UNWRAPPED inside the per-row nightly upsert mapping,
        # so this must never raise (a non-str .strip() AttributeError would kill the
        # whole NAV refresh). Treat anything that is not a str as empty/unclassifiable.
        return None
    s = raw.strip()
    if not s:
        return None
    s = s.translate(_CURLY_APOSTROPHES)
    s = _WS_RUN.sub(" ", s)
    return s


# ---------------------------------------------------------------------------
# Classification result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CategoryValidation:
    """Result of classifying one raw ``mf_funds.category`` string.

    Fields
    ------
    raw
        The original unmodified string (or None) as read from the AMFI feed.
    normalized
        The result of :func:`normalize` applied to ``raw``; None when raw is
        None / blank.
    status
        One of ``"canonical"`` / ``"legacy"`` / ``"unknown"`` / ``"empty"``.

        * ``canonical`` — normalized matches a SEBI leaf (directly or via
          :data:`_LEGACY_MAP`); ``canonical`` field is populated.
        * ``legacy`` — recognized old/ambiguous bare header in
          :data:`_LEGACY_UNMAPPABLE`; not auto-mapped; ``canonical`` is None.
        * ``unknown`` — not recognized at all; may indicate AMFI taxonomy drift;
          ``canonical`` is None.
        * ``empty`` — raw is None or whitespace-only.
    canonical
        The SEBI-canonical leaf string to store in ``mf_funds.sebi_category``,
        or None when the status is not ``"canonical"``.
    scheme_class
        The class prefix (e.g. ``"Equity Scheme"``, ``"Debt Scheme"``) derived
        from the canonical leaf's ``"<class> - <sub>"`` structure, or None.
    """

    raw: str | None
    normalized: str | None
    status: str
    canonical: str | None
    scheme_class: str | None


def classify(raw: str | None) -> CategoryValidation:
    """Classify one raw category string against the SEBI taxonomy.

    Returns a :class:`CategoryValidation` whose ``status`` is one of
    ``"canonical"`` / ``"legacy"`` / ``"unknown"`` / ``"empty"``.
    Never raises; designed to be called in a tight ingestion loop.
    """
    norm = normalize(raw)

    if norm is None:
        return CategoryValidation(
            raw=raw,
            normalized=None,
            status="empty",
            canonical=None,
            scheme_class=None,
        )

    # Direct canonical match
    if norm in _CANONICAL_LEAVES:
        scheme_class = norm.split(" - ", 1)[0]
        return CategoryValidation(
            raw=raw,
            normalized=norm,
            status="canonical",
            canonical=norm,
            scheme_class=scheme_class,
        )

    # Legacy map (unambiguous bare → canonical)
    if norm in _LEGACY_MAP:
        canonical = _LEGACY_MAP[norm]
        scheme_class = canonical.split(" - ", 1)[0]
        return CategoryValidation(
            raw=raw,
            normalized=norm,
            status="canonical",
            canonical=canonical,
            scheme_class=scheme_class,
        )

    # Recognized unmappable bare header (ambiguous legacy)
    if norm in _LEGACY_UNMAPPABLE:
        return CategoryValidation(
            raw=raw,
            normalized=norm,
            status="legacy",
            canonical=None,
            scheme_class=None,
        )

    # Unrecognized — possible AMFI taxonomy drift
    return CategoryValidation(
        raw=raw,
        normalized=norm,
        status="unknown",
        canonical=None,
        scheme_class=None,
    )


def canonical_for(raw: str | None) -> str | None:
    """Return the canonical SEBI leaf for ``raw``, or None if not resolvable.

    Convenience wrapper around :func:`classify`; this is the value to store in
    ``mf_funds.sebi_category``.
    """
    return classify(raw).canonical


# ---------------------------------------------------------------------------
# Plan / option parsing (B67 Task 3)
# ---------------------------------------------------------------------------

# Order matters — more-specific patterns before their substrings.
# "idcw reinvest" matches before "idcw" so "IDCW Reinvestment" maps correctly.
# "dividend reinvest" similarly before bare "dividend".
# "growth" is last — it appears in many fund names (e.g. "Growth Fund"); we
# only fall through to it when no IDCW/dividend variant is present.
_OPTION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("idcw reinvest",    "dividend_reinvest"),
    ("idcw re-invest",   "dividend_reinvest"),
    ("idcw payout",      "dividend_payout"),
    ("idcw",             "idcw"),
    ("dividend reinvest","dividend_reinvest"),
    ("dividend re-invest","dividend_reinvest"),
    ("dividend payout",  "dividend_payout"),
    ("dividend",         "idcw"),   # bare 'dividend' → idcw (post-2021 SEBI rename)
    ("growth",           "growth"),
)


def parse_plan_option(scheme_name: str | None) -> tuple[str | None, str | None]:
    """Return (plan_type, option_type) parsed from an AMFI scheme name.

    Pure function — no DB access, no network calls.

    plan_type : ``'direct'`` | ``'regular'`` | ``'retail'`` | ``'institutional'``
                | ``None``
    option_type: ``'growth'`` | ``'idcw'`` | ``'dividend_reinvest'`` |
                 ``'dividend_payout'`` | ``None``

    Rules are applied case-insensitively. ``None`` is returned when the
    scheme name does not contain a recognisable marker — common for legacy
    schemes whose names predate the Direct/Regular bifurcation (2013).

    Precedence (B72 follow-up): ``direct`` / ``regular`` (the modern post-2013
    bifurcation) win over the older ``retail`` / ``institutional`` plan classes,
    which only surface on legacy/closed schemes that carry no Direct/Regular tag.
    Neither raises nor modifies the input.
    """
    if not isinstance(scheme_name, str) or not scheme_name.strip():
        return None, None

    lower = scheme_name.lower()

    # plan_type: first match wins, modern bifurcation (direct/regular) first.
    plan_type: str | None = None
    if "direct" in lower:
        plan_type = "direct"
    elif "regular" in lower:
        plan_type = "regular"
    elif "institutional" in lower:
        plan_type = "institutional"
    elif "retail" in lower:
        plan_type = "retail"

    # option_type: first pattern in _OPTION_PATTERNS wins
    option_type: str | None = None
    for pattern, value in _OPTION_PATTERNS:
        if pattern in lower:
            option_type = value
            break

    return plan_type, option_type


# ---------------------------------------------------------------------------
# IDCW frequency parsing + short-name derivation (fund_name_short, B72 follow-up)
# ---------------------------------------------------------------------------

# IDCW / dividend payout frequencies. Order matters: multi-word tokens
# ("half yearly") before their substrings; "annual" matches "annually" and
# "annual" alike. Maps the surface token → the canonical frequency value.
# These words essentially never appear in a fund's brand name except as the
# payout cadence of an income-distribution option, so a standalone match is safe.
_FREQUENCY_PATTERNS: tuple[tuple[str, str], ...] = (
    ("half yearly",  "half_yearly"),
    ("half-yearly",  "half_yearly"),
    ("semi annual",  "half_yearly"),
    ("semi-annual",  "half_yearly"),
    ("fortnightly",  "fortnightly"),
    ("quarterly",    "quarterly"),
    ("monthly",      "monthly"),
    ("weekly",       "weekly"),
    ("daily",        "daily"),
    ("annually",     "annual"),
    ("annual",       "annual"),
    ("yearly",       "annual"),
)


def parse_idcw_frequency(scheme_name: str | None) -> str | None:
    """Return the IDCW/dividend payout frequency from an AMFI scheme name.

    Pure function. Returns one of ``'daily'`` | ``'weekly'`` | ``'fortnightly'``
    | ``'monthly'`` | ``'quarterly'`` | ``'half_yearly'`` | ``'annual'`` |
    ``None``.

    Kept SEPARATE from :func:`parse_plan_option` (rather than widening its stable
    two-tuple contract, which the nightly upsert + 30 tests depend on). Frequency
    is only meaningful for an IDCW / dividend option; a pure Growth name yields
    ``None``. Neither raises nor modifies the input.
    """
    if not isinstance(scheme_name, str) or not scheme_name.strip():
        return None
    lower = scheme_name.lower()
    for pattern, value in _FREQUENCY_PATTERNS:
        if pattern in lower:
            return value
    return None


# Tokens that are pure plan/option/frequency noise — never part of a brand name.
# A trailing run of these (after splitting off a " - " segment) is droppable.
# All lower-case; matched against lower-cased, punctuation-stripped tokens.
_NOISE_TOKENS: frozenset[str] = frozenset(
    {
        # plan
        "direct", "regular", "retail", "institutional", "plan", "option",
        # option
        "growth", "idcw", "dividend", "reinvestment", "reinvest", "re-invest",
        "payout", "bonus",
        # income-distribution-cum-capital-withdrawal long form
        "income", "distribution", "cum", "capital", "withdrawal",
        # frequency
        "daily", "weekly", "fortnightly", "monthly", "quarterly",
        "half", "yearly", "half-yearly", "annual", "annually", "semi", "semi-annual",
    }
)

# Strip a leading "(Formerly ...)" / "(Formerly Known As ...)" parenthetical and
# any other leading/trailing parenthetical the AMFI feed sometimes prepends. We
# only remove parentheticals that are clearly NOT brand — "(Formerly ...)" — to
# stay conservative; other parentheticals are left in place.
_FORMERLY_RE = re.compile(r"\(\s*formerly[^)]*\)", re.IGNORECASE)
# Punctuation to strip from a token before testing it against _NOISE_TOKENS.
_TOKEN_STRIP = " \t-–—.,;:"


def _segment_is_all_noise(segment: str) -> bool:
    """True when every word in a " - "-delimited segment is plan/option/frequency
    noise (so the whole segment can be dropped from the display name)."""
    words = [w.strip(_TOKEN_STRIP).lower() for w in segment.split()]
    words = [w for w in words if w]
    if not words:
        return True
    return all(w in _NOISE_TOKENS for w in words)


# Module-level cache for the operator override map (loaded lazily, once).
_OVERRIDES_CACHE: dict[str, dict[str, str]] | None = None


def _load_overrides() -> dict[str, dict[str, str]]:
    """Load the operator-curated short-name overrides from the JSON seed file.

    Shape: ``{"by_isin": {<isin>: <short>}, "by_scheme_name": {<name>: <short>}}``.
    Loaded once and cached. Fails SAFE to empty maps on any error — a malformed or
    missing override file must never break the nightly ingestion upsert.
    """
    global _OVERRIDES_CACHE
    if _OVERRIDES_CACHE is not None:
        return _OVERRIDES_CACHE
    import json
    from pathlib import Path

    by_isin: dict[str, str] = {}
    by_name: dict[str, str] = {}
    try:
        path = Path(__file__).with_name("fund_name_overrides.json")
        raw = json.loads(path.read_text(encoding="utf-8"))
        by_isin = {str(k): str(v) for k, v in (raw.get("by_isin") or {}).items()}
        # Normalize override scheme-name keys so a feed whitespace/curly-quote
        # variation still hits the pin.
        by_name = {
            (normalize(k) or "").lower(): str(v)
            for k, v in (raw.get("by_scheme_name") or {}).items()
        }
    except Exception:  # noqa: BLE001 — override file is best-effort, never fatal
        by_isin, by_name = {}, {}
    _OVERRIDES_CACHE = {"by_isin": by_isin, "by_scheme_name": by_name}
    return _OVERRIDES_CACHE


def derive_short_name(scheme_name: str | None, isin: str | None = None) -> str | None:
    """Return a clean, display-only short name for an AMFI scheme name.

    Pure function (the override map is loaded once from a checked-in JSON file —
    no DB, no network). This is the SINGLE source of truth for the short name;
    backend and frontend both read the column it populates, so neither re-derives.

    Resolution order:

    1. **Operator override** — keyed by ``isin`` first, then by the exact
       (normalized) ``scheme_name``. Lets an operator PIN a clean name when the
       heuristic is wrong (``fund_name_overrides.json``).
    2. **Conservative heuristic** — strip a leading ``(Formerly …)`` parenthetical,
       then drop trailing ``" - "`` segments that are ENTIRELY plan/option/frequency
       noise (Direct/Regular/Retail · Growth/IDCW/Dividend · Reinvestment/Payout ·
       Monthly/Quarterly/…), and trim a trailing run of noise words from the last
       kept segment. Brand words are NEVER stripped, and the first segment is always
       kept.
    3. **Fail safe** — if stripping would leave nothing (or the input is empty), the
       ORIGINAL scheme name is returned unchanged. ``None`` only for a None/blank input.

    ``scheme_name`` itself stays the immutable official AMFI name — this value is
    display-only and never replaces it on Fund Detail / tooltip / export / reports.
    """
    if not isinstance(scheme_name, str) or not scheme_name.strip():
        return None

    overrides = _load_overrides()
    if isin and isin in overrides["by_isin"]:
        return overrides["by_isin"][isin]
    name_key = (normalize(scheme_name) or "").lower()
    if name_key in overrides["by_scheme_name"]:
        return overrides["by_scheme_name"][name_key]

    # 1. Drop a "(Formerly ...)" parenthetical, then normalize whitespace.
    cleaned = _FORMERLY_RE.sub(" ", scheme_name)
    cleaned = normalize(cleaned) or ""
    if not cleaned:
        return scheme_name.strip()

    # 2. Split on " - " and keep the first segment (brand+fund) plus any later
    #    segment that carries real (non-noise) words. Drop pure-noise segments.
    segments = [s.strip() for s in cleaned.split(" - ")]
    kept: list[str] = [segments[0]] if segments else []
    for seg in segments[1:]:
        if not _segment_is_all_noise(seg):
            kept.append(seg)

    result = " - ".join(s for s in kept if s).strip()

    # 3. Trim a trailing run of noise words from the LAST kept segment (handles
    #    names with no " - " separators, e.g. "Axis ELSS Tax Saver Fund Direct
    #    Growth"). Stop at the first non-noise word from the right so brand words
    #    are never lost.
    words = result.split()
    while words and words[-1].strip(_TOKEN_STRIP).lower() in _NOISE_TOKENS:
        words.pop()
    result = " ".join(words).strip(_TOKEN_STRIP).strip()

    # Fail safe — never return an empty / over-stripped name.
    return result if result else scheme_name.strip()


# ---------------------------------------------------------------------------
# Batch summarizer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationSummary:
    """Aggregate validation result over a batch of raw category strings.

    Fields
    ------
    total
        Number of input strings processed (including None / blank).
    counts
        Per-status tallies: ``{"canonical": N, "legacy": N, "unknown": N,
        "empty": N}``.
    unknown_samples
        Up to 20 distinct raw values (sorted) whose status is ``"unknown"``.
        Useful for detecting AMFI taxonomy drift in worker logs.
    legacy_samples
        Up to 20 distinct raw values (sorted) whose status is ``"legacy"``.
    """

    total: int
    counts: dict[str, int]
    unknown_samples: list[str]
    legacy_samples: list[str]


def summarize(raws: Iterable[str | None]) -> ValidationSummary:
    """Tally classification results across a batch of raw category strings.

    Collects up to 20 DISTINCT raw values for ``"unknown"`` and ``"legacy"``
    statuses (sorted) so callers can log them as observability samples.
    """
    counts: dict[str, int] = {"canonical": 0, "legacy": 0, "unknown": 0, "empty": 0}
    unknown_set: set[str] = set()
    legacy_set: set[str] = set()
    total = 0

    for raw in raws:
        total += 1
        result = classify(raw)
        counts[result.status] = counts.get(result.status, 0) + 1
        if result.status == "unknown" and raw is not None:
            unknown_set.add(raw)
        elif result.status == "legacy" and raw is not None:
            legacy_set.add(raw)

    unknown_samples = sorted(unknown_set)[:20]
    legacy_samples = sorted(legacy_set)[:20]

    return ValidationSummary(
        total=total,
        counts=counts,
        unknown_samples=unknown_samples,
        legacy_samples=legacy_samples,
    )
