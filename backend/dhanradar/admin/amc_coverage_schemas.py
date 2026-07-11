"""
DhanRadar — Admin AMC data-coverage schemas.

Backs GET /admin/amc/coverage: ONE aggregation endpoint reporting per-AMC ×
per-field DATA COVERAGE (row counts / percentages only — never a fund score,
rating, or quality judgement; DhanRadar's compliance boundary keeps this
strictly operational/ingestion telemetry, same as admin/ops_schemas.py).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# The 8 tracked enrichment fields (fixed order — also the column order the FE renders).
# `category` (2026-07-08 addition) is DIFFERENT from the other 7: it is populated by
# ONE platform-wide pipeline (mf_scheme_master_refresh, from AMFI's own scheme master),
# never a per-AMC scraper/manual upload — so it never gets a mode/freq classification
# (_SOURCE_CLASS has no "category" entries; every cell renders as a bare count). It
# never influences the source_tag badge either, since a "-" mode is ignored by
# _source_tag_for. It is tracked because `sebi_category` is the validated field
# cohort-grouping/scoring depends on (ADR-0034) — a null value is a real, actionable
# data-quality gap, just not an AMC-specific one.
CoverageField = Literal[
    "constituents",
    "aum",
    "ter",
    "riskometer",
    "benchmark",
    "manager",
    "exit_load",
    "category",
]

FIELD_ORDER: tuple[CoverageField, ...] = (
    "constituents",
    "aum",
    "ter",
    "riskometer",
    "benchmark",
    "manager",
    "exit_load",
    "category",
)

FIELD_LABELS: dict[CoverageField, str] = {
    "constituents": "Constituents",
    "aum": "AUM",
    "ter": "TER",
    "riskometer": "Riskometer",
    "benchmark": "Benchmark",
    "manager": "Manager",
    "exit_load": "Exit load",
    "category": "Category",
}


class CoverageCell(BaseModel):
    """One AMC × field cell. `covered_count` is a live DB count (always accurate).
    `mode`/`freq` are best-effort metadata from a static classification table —
    see amc_coverage_router._SOURCE_CLASS — kept separate from covered_count so a
    stale classification can never distort the real coverage number."""

    covered_count: int
    mode: Literal["A", "ML", "-"]  # Automatic scraper / Manual upload / none
    freq: Literal[
        "Y", "Q", "W", "M", "D", "O", "-"
    ]  # yearly/quarterly/weekly/monthly/daily/once/none


class AmcCoverageRow(BaseModel):
    amc_name: (
        str  # full AMFI-registered name (never hidden — compliance: full name always available)
    )
    short_name: str  # display name for the compact table, e.g. "HDFC", "ICICI Pru"
    fund_count: int  # DISTINCT SCHEMES for this AMC (Growth/IDCW/Direct/Regular plan-variant ISINs of the same scheme count once — see amc_coverage_router._SCHEME_KEY)
    fields: dict[CoverageField, CoverageCell]
    completeness_pct: float  # equal-weighted average across the 8 fields, 0-100
    # Overall per-AMC source classification, derived from this row's own `fields`
    # modes (see amc_coverage_router._source_tag_for) — shown as a badge next to
    # the AMC name so "which AMCs are automated vs manual" is a glance, not a
    # per-cell scan. "none" when no field has a known source yet (e.g. staged
    # but not yet uploaded).
    source_tag: Literal["auto", "manual", "mixed", "none"]
    # Staleness indicator (2026-07-08 addition): the most recent SEBI monthly
    # disclosure month we have processed for this AMC — the later of
    # MAX(mf_funds.aum_as_of) and MAX(mf_fund_constituents.as_of_month) across
    # the AMC's schemes. None if the AMC has neither yet (never disclosed/
    # processed). This measures DISCLOSURE freshness ("how current is the data
    # we hold"), not pipeline-run freshness ("did our scraper run today") —
    # see amc_coverage_router._compute_staleness for the exact derivation.
    last_updated: str | None  # ISO date (YYYY-MM-DD), or None
    staleness_days: int | None  # today - last_updated in days, or None


class CoverageSummary(BaseModel):
    total_amcs: int
    total_funds: (
        int  # DISTINCT SCHEMES platform-wide, not raw ISIN rows (see AmcCoverageRow.fund_count)
    )
    nfo_count: int  # distinct schemes with launch_date >= as_of - 180 days
    accuracy_pct: float  # ingestion success rate: parsed / (parsed + failed)
    overall_completeness_pct: float  # fund-weighted average of per-AMC completeness_pct
    as_of: str  # ISO timestamp


class CoverageMeta(BaseModel):
    """Every definition the page must state verbatim (founder spec: "State every
    definition in the response meta + a HelpTip on the page")."""

    field_labels: dict[CoverageField, str]
    field_order: list[CoverageField]
    nfo_definition: str = "Schemes with a launch_date within the last 180 days."
    accuracy_definition: str = (
        "Ingestion success rate: manual-ingest files parsed / (parsed + failed), "
        "all-time. Not a fund-quality or scoring metric."
    )
    completeness_definition: str = (
        "Per AMC: average, across the 8 tracked fields, of the fraction of that "
        "AMC's SCHEMES (Growth/IDCW/Direct/Regular plan-variant ISINs of the same "
        "scheme counted once) with a non-null value for the field on at least one "
        "of their ISINs. Overall: the scheme-count-weighted average of every AMC's "
        "completeness_pct."
    )
    mode_definition: str = "A = automatic scraper · ML = manual upload · - = no source yet."
    freq_definition: str = (
        "Y = yearly · W = weekly · M = monthly · D = daily · O = once · - = none."
    )
    category_definition: str = (
        "Coverage of mf_funds.sebi_category (the validated SEBI category cohort "
        "grouping/scoring depends on — ADR-0034). Populated by ONE platform-wide "
        "pipeline (AMFI scheme master), not a per-AMC scraper/manual upload, so "
        "this column never carries a mode/freq tag — a gap here still means real, "
        "actionable schemes that can't be cohort-compared yet."
    )
    staleness_definition: str = (
        "Updated = the later of MAX(aum_as_of) and MAX(constituents as_of_month) "
        "across the AMC's schemes — how current the DISCLOSED data is, not whether "
        "our pipeline ran recently. None = this AMC has neither yet."
    )
    source_tag_definition: str = (
        "Badge next to the AMC name: auto = every field with a known source is "
        "automatic · manual = every field with a known source is a manual upload · "
        "mixed = some fields automatic and some manual · no badge = no field has a "
        "known source yet."
    )
    disclaimer: str = (
        "Data-coverage counts only. No fund score, rating, or recommendation is shown "
        "or implied on this page."
    )


class AmcCoverageResponse(BaseModel):
    summary: CoverageSummary
    rows: list[AmcCoverageRow]
    meta: CoverageMeta
