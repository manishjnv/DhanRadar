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

# The 7 tracked enrichment fields (fixed order — also the column order the FE renders).
CoverageField = Literal[
    "constituents",
    "aum",
    "ter",
    "riskometer",
    "benchmark",
    "manager",
    "exit_load",
]

FIELD_ORDER: tuple[CoverageField, ...] = (
    "constituents",
    "aum",
    "ter",
    "riskometer",
    "benchmark",
    "manager",
    "exit_load",
)

FIELD_LABELS: dict[CoverageField, str] = {
    "constituents": "Constituents",
    "aum": "AUM",
    "ter": "TER",
    "riskometer": "Riskometer",
    "benchmark": "Benchmark",
    "manager": "Manager",
    "exit_load": "Exit load",
}


class CoverageCell(BaseModel):
    """One AMC × field cell. `covered_count` is a live DB count (always accurate).
    `mode`/`freq` are best-effort metadata from a static classification table —
    see amc_coverage_router._SOURCE_CLASS — kept separate from covered_count so a
    stale classification can never distort the real coverage number."""

    covered_count: int
    mode: Literal["A", "M", "-"]  # Automatic scraper / Manual upload / none
    freq: Literal["Y", "W", "M", "D", "O", "-"]  # yearly/weekly/monthly/daily/once/none


class AmcCoverageRow(BaseModel):
    amc_name: (
        str  # full AMFI-registered name (never hidden — compliance: full name always available)
    )
    short_name: str  # display name for the compact table, e.g. "HDFC", "ICICI Pru"
    fund_count: int  # DISTINCT SCHEMES for this AMC (Growth/IDCW/Direct/Regular plan-variant ISINs of the same scheme count once — see amc_coverage_router._SCHEME_KEY)
    fields: dict[CoverageField, CoverageCell]
    completeness_pct: float  # equal-weighted average across the 7 fields, 0-100


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
        "Per AMC: average, across the 7 tracked fields, of the fraction of that "
        "AMC's SCHEMES (Growth/IDCW/Direct/Regular plan-variant ISINs of the same "
        "scheme counted once) with a non-null value for the field on at least one "
        "of their ISINs. Overall: the scheme-count-weighted average of every AMC's "
        "completeness_pct."
    )
    mode_definition: str = "A = automatic scraper · M = manual upload · - = no source yet."
    freq_definition: str = (
        "Y = yearly · W = weekly · M = monthly · D = daily · O = once · - = none."
    )
    disclaimer: str = (
        "Data-coverage counts only. No fund score, rating, or recommendation is shown "
        "or implied on this page."
    )


class AmcCoverageResponse(BaseModel):
    summary: CoverageSummary
    rows: list[AmcCoverageRow]
    meta: CoverageMeta
