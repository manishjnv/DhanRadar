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

#: The single ELSS/tax-saver leaf's canonical string (must match the member of
#: `_CANONICAL_LEAVES` above) — the SEBI-mandated 3-year per-lot lock-in applies only to
#: holdings in this exact category (P2, `mf/portfolio_read.py::compute_elss_lockin`).
ELSS_CATEGORY = "Equity Scheme - ELSS"

# ---------------------------------------------------------------------------
# Legacy maps
# ---------------------------------------------------------------------------

# Unambiguous bare-header → canonical leaf.  Only strings that map to exactly
# one SEBI leaf are placed here; ambiguous ones go to _LEGACY_UNMAPPABLE.
_LEGACY_MAP: dict[str, str] = {
    "ELSS": "Equity Scheme - ELSS",
}

# Recognized old/ambiguous bare headers that we deliberately do NOT auto-map
# FROM THE HEADER ALONE. "Gilt" is ambiguous between two SEBI Gilt leaves;
# "Growth" / "Income" / "Money Market" are pre-rationalization umbrella names
# with no single mapping. B66 extension (2026-07-10): the nightly writer now
# falls back to infer_category_from_name() for these — the SCHEME NAME usually
# states the category unambiguously even when the header is an umbrella.
_LEGACY_UNMAPPABLE: frozenset[str] = frozenset({"Gilt", "Growth", "Income", "Money Market"})

# AMFI presentation variants: the feed sometimes emits a different CLASS
# prefix for the same SEBI leaf ("Income/Debt Oriented Schemes - Liquid Fund",
# live DB evidence 2026-07-10). Rewritten to the canonical class prefix and
# re-checked against the leaf set — never a guess.
_CLASS_PREFIX_ALIASES: dict[str, str] = {
    "Income/Debt Oriented Schemes": "Debt Scheme",
    "Growth/Equity Oriented Schemes": "Equity Scheme",
    "Hybrid Schemes": "Hybrid Scheme",
    "Solution Oriented Schemes": "Solution Oriented Scheme",
    "Other Schemes": "Other Scheme",
}

# Exact-string oddball variants seen in the live DB (2026-07-10 tally of
# sebi_category-NULL rows) that don't follow the "<class> - <leaf>" shape.
_VARIANT_MAP: dict[str, str] = {
    "Index Funds - Equity Funds": "Other Scheme - Index Funds",
    "Exchange Traded Funds (ETFs) - Equity ETF": "Other Scheme - Other ETFs",
    "Exchange Traded Funds (ETFs) - Gold ETF": "Other Scheme - Gold ETF",
    "Fund of Funds Scheme (Domestic) - Fund of Funds Scheme (Domestic)": (
        "Other Scheme - FoF Domestic"
    ),
    "Fund of Funds Scheme (Overseas) - Fund of Funds Scheme (Overseas)": (
        "Other Scheme - FoF Overseas"
    ),
}

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

    # Presentation-variant class prefix ("Income/Debt Oriented Schemes - X")
    # → canonical prefix, accepted ONLY when the rewrite lands on a real leaf.
    if " - " in norm:
        prefix, leaf = norm.split(" - ", 1)
        alias = _CLASS_PREFIX_ALIASES.get(prefix)
        if alias:
            candidate = f"{alias} - {leaf}"
            if candidate in _CANONICAL_LEAVES:
                return CategoryValidation(
                    raw=raw,
                    normalized=norm,
                    status="canonical",
                    canonical=candidate,
                    scheme_class=alias,
                )
    if norm in _VARIANT_MAP:
        canonical = _VARIANT_MAP[norm]
        return CategoryValidation(
            raw=raw,
            normalized=norm,
            status="canonical",
            canonical=canonical,
            scheme_class=canonical.split(" - ", 1)[0],
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


# ---------------------------------------------------------------------------
# Name-based category inference (B66 extension, 2026-07-10)
# ---------------------------------------------------------------------------
# For funds whose HEADER is a pre-2018 umbrella ("Income": 5,220 live rows,
# "Growth": 299) the scheme NAME usually states the category unambiguously.
# Deliberately CONSERVATIVE: only tokens that map to exactly one SEBI leaf are
# listed; anything ambiguous (sectoral themes, bare "value", FoF direction
# without an overseas marker) yields None. ORDER MATTERS — ETF/index checks
# run FIRST so "BSE Liquid Rate ETF" never hits the "liquid" debt token, and
# multi-word debt tokens run before their single-word substrings.

_NAME_RULES: tuple[tuple[str, str], ...] = (
    # ETFs / index funds first — their names often contain debt-like words.
    ("gold etf", "Other Scheme - Gold ETF"),
    ("silver etf", "Other Scheme - Other ETFs"),
    ("etf", "Other Scheme - Other ETFs"),
    ("index fund", "Other Scheme - Index Funds"),
    ("fund of fund", "__FOF__"),
    ("fof", "__FOF__"),
    # Solution oriented
    ("retirement", "Solution Oriented Scheme - Retirement Fund"),
    ("children", "Solution Oriented Scheme - Children's Fund"),
    # Hybrid (multi-word, unambiguous)
    ("arbitrage", "Hybrid Scheme - Arbitrage Fund"),
    ("balanced advantage", "Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage"),
    ("dynamic asset allocation", "Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage"),
    ("equity savings", "Hybrid Scheme - Equity Savings"),
    ("aggressive hybrid", "Hybrid Scheme - Aggressive Hybrid Fund"),
    ("equity hybrid", "Hybrid Scheme - Aggressive Hybrid Fund"),
    ("conservative hybrid", "Hybrid Scheme - Conservative Hybrid Fund"),
    ("debt hybrid", "Hybrid Scheme - Conservative Hybrid Fund"),
    ("multi asset", "Hybrid Scheme - Multi Asset Allocation"),
    # Debt (multi-word before single-word)
    ("banking and psu", "Debt Scheme - Banking and PSU Fund"),
    ("banking & psu", "Debt Scheme - Banking and PSU Fund"),
    ("corporate bond", "Debt Scheme - Corporate Bond Fund"),
    ("credit risk", "Debt Scheme - Credit Risk Fund"),
    ("dynamic bond", "Debt Scheme - Dynamic Bond"),
    ("floating rate", "Debt Scheme - Floater Fund"),
    ("floater", "Debt Scheme - Floater Fund"),
    ("money market", "Debt Scheme - Money Market Fund"),
    ("ultra short", "Debt Scheme - Ultra Short Duration Fund"),
    ("low duration", "Debt Scheme - Low Duration Fund"),
    ("medium to long duration", "Debt Scheme - Medium to Long Duration Fund"),
    ("medium duration", "Debt Scheme - Medium Duration Fund"),
    ("medium term", "Debt Scheme - Medium Duration Fund"),
    ("long duration", "Debt Scheme - Long Duration Fund"),
    ("short duration", "Debt Scheme - Short Duration Fund"),
    ("short term fund", "Debt Scheme - Short Duration Fund"),
    ("short term debt", "Debt Scheme - Short Duration Fund"),
    ("constant maturity gilt", "Debt Scheme - Gilt Fund with 10 year constant duration"),
    ("gilt fund with 10 year", "Debt Scheme - Gilt Fund with 10 year constant duration"),
    # Target-maturity "Gilt Index"/"SDL Index" funds are INDEX funds, not
    # actively-managed gilt (their names rarely say "index fund" contiguously:
    # "SBI CRISIL IBX Gilt Index- June 2036 Fund").
    ("gilt index", "Other Scheme - Index Funds"),
    ("sdl index", "Other Scheme - Index Funds"),
    ("g-sec index", "Other Scheme - Index Funds"),
    ("gilt", "Debt Scheme - Gilt Fund"),
    ("overnight", "Debt Scheme - Overnight Fund"),
    ("liquid", "Debt Scheme - Liquid Fund"),
    # Equity (unambiguous cap-style / mandate tokens only — sectoral is NEVER
    # inferred; theme names are open-ended)
    ("elss", "Equity Scheme - ELSS"),
    ("tax saver", "Equity Scheme - ELSS"),
    ("taxgain", "Equity Scheme - ELSS"),
    ("large & mid cap", "Equity Scheme - Large & Mid Cap Fund"),
    ("large and mid cap", "Equity Scheme - Large & Mid Cap Fund"),
    ("large cap", "Equity Scheme - Large Cap Fund"),
    ("largecap", "Equity Scheme - Large Cap Fund"),
    ("mid cap", "Equity Scheme - Mid Cap Fund"),
    ("midcap", "Equity Scheme - Mid Cap Fund"),
    ("small cap", "Equity Scheme - Small Cap Fund"),
    ("smallcap", "Equity Scheme - Small Cap Fund"),
    ("flexi cap", "Equity Scheme - Flexi Cap Fund"),
    ("flexicap", "Equity Scheme - Flexi Cap Fund"),
    ("multi cap", "Equity Scheme - Multi Cap Fund"),
    ("multicap", "Equity Scheme - Multi Cap Fund"),
    ("focused", "Equity Scheme - Focused Fund"),
    ("contra", "Equity Scheme - Contra Fund"),
    ("dividend yield", "Equity Scheme - Dividend Yield Fund"),
)

_OVERSEAS_MARKERS = (
    "overseas",
    "global",
    "international",
    "world",
    "nasdaq",
    "us equity",
    "u.s.",
    "s&p 500",
    "emerging market",
    "foreign",
    "brazil",
    "china",
    "japan",
    "europe",
)


def infer_category_from_name(scheme_name: str | None) -> str | None:
    """Infer the SEBI leaf from a scheme NAME — pure, conservative, fail-closed.

    Used by the nightly writer ONLY when the raw header did not classify
    (pre-2018 umbrella headers — B66). First matching rule wins; rules are
    ordered so ETF/index tokens shadow debt words inside ETF names and
    multi-word tokens shadow their substrings. Returns None when nothing
    unambiguous matches (sectoral/thematic equity is never inferred).
    """
    if not isinstance(scheme_name, str) or not scheme_name.strip():
        return None
    lower = " ".join(scheme_name.lower().split())
    for token, leaf in _NAME_RULES:
        if token in lower:
            if leaf == "__FOF__":
                overseas = any(m in lower for m in _OVERSEAS_MARKERS)
                return "Other Scheme - FoF Overseas" if overseas else "Other Scheme - FoF Domestic"
            return leaf
    return None


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
    ("idcw reinvest", "dividend_reinvest"),
    ("idcw re-invest", "dividend_reinvest"),
    ("idcw payout", "dividend_payout"),
    ("idcw", "idcw"),
    ("dividend reinvest", "dividend_reinvest"),
    ("dividend re-invest", "dividend_reinvest"),
    ("dividend payout", "dividend_payout"),
    ("dividend", "idcw"),  # bare 'dividend' → idcw (post-2021 SEBI rename)
    ("growth", "growth"),
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
    ("half yearly", "half_yearly"),
    ("half-yearly", "half_yearly"),
    ("semi annual", "half_yearly"),
    ("semi-annual", "half_yearly"),
    ("fortnightly", "fortnightly"),
    ("quarterly", "quarterly"),
    ("monthly", "monthly"),
    ("weekly", "weekly"),
    ("daily", "daily"),
    ("annually", "annual"),
    ("annual", "annual"),
    ("yearly", "annual"),
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
        "direct",
        "regular",
        "retail",
        "institutional",
        "plan",
        "option",
        # option
        "growth",
        "idcw",
        "dividend",
        "reinvestment",
        "reinvest",
        "re-invest",
        "payout",
        "bonus",
        # income-distribution-cum-capital-withdrawal long form
        "income",
        "distribution",
        "cum",
        "capital",
        "withdrawal",
        # frequency
        "daily",
        "weekly",
        "fortnightly",
        "monthly",
        "quarterly",
        "half",
        "yearly",
        "half-yearly",
        "annual",
        "annually",
        "semi",
        "semi-annual",
    }
)

# Strip a leading "(Formerly ...)" / "(Formerly Known As ...)" parenthetical and
# any other leading/trailing parenthetical the AMFI feed sometimes prepends. We
# only remove parentheticals that are clearly NOT brand — "(Formerly ...)" — to
# stay conservative; other parentheticals are left in place.
_FORMERLY_RE = re.compile(r"\(\s*formerly[^)]*\)", re.IGNORECASE)
# Punctuation to strip from a token before testing it against _NOISE_TOKENS.
_TOKEN_STRIP = " \t-–—.,;:"
# Connector/filler words that join option long-forms ("Payout OF Income
# Distribution …", "… cum Capital Withdrawal"). They never legitimately END a
# clean brand (brands end in Fund/ETF/Scheme/Series/Plan-N), so inside the
# trailing noise run they are consumed like noise — without them a single 'of'
# stops the scan and leaves "… Plan - Payout of". A connector is only ever reached
# when everything to its RIGHT is already noise, so "State Bank of India Fund" and
# "Fund of Fund" are safe (the scan stops at the brand's 'Fund' first).
_CONNECTOR_TOKENS: frozenset[str] = frozenset(
    {"of", "the", "and", "a", "an", "for", "to", "with", "cum", "from"}
)

# A "word" run for the right-scan trailing strip. Hyphen and slash are NOT in the
# class, so the live-feed's un-spaced separators ("Fund-Direct", "Plan-Growth",
# "Payout/Reinvestment") tokenize into distinct words while brand-internal hyphens
# ("Mid-Cap") survive — the scan only ever cuts by character index, never rejoins,
# so interior punctuation in the kept prefix is preserved.
_WORD_RE = re.compile(r"[A-Za-z0-9&'.()]+")


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
       then scan from the RIGHT dropping a trailing run of plan/option/frequency
       noise tokens (Direct/Regular/Retail/Institutional · Growth/IDCW/Dividend ·
       Reinvestment/Payout/Bonus · the Income-Distribution-cum-Capital-Withdrawal
       long form · Daily/Monthly/…), stopping at the first BRAND word. Tokens split
       on whitespace AND hyphens so the feed's un-spaced separators
       ("Fund-Direct Plan-Growth") are handled, while brand-internal hyphens
       ("Mid-Cap") survive because the cut is by character index, never a rejoin.
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

    # 2. Right-scan: drop the trailing run of plan/option/frequency noise tokens,
    #    cutting at the character offset just before the last surviving noise word.
    #    Stops at the first non-noise (brand) word, e.g. "Fund"/"ETF"/"Index".
    matches = list(_WORD_RE.finditer(cleaned))
    cut = len(cleaned)
    for m in reversed(matches):
        key = m.group(0).strip(_TOKEN_STRIP + "()").lower()
        if key == "" or key in _NOISE_TOKENS or key in _CONNECTOR_TOKENS:
            cut = m.start()
            continue
        break
    result = cleaned[:cut].strip(_TOKEN_STRIP).strip()

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
