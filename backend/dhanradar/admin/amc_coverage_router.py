"""
DhanRadar — Admin AMC data-coverage router.

GET /admin/amc/coverage (RequireAdmin) — ONE aggregation endpoint reporting, per
AMC and per tracked enrichment field (Constituents/AUM/TER/Riskometer/Benchmark/
Manager/Exit load), how many of that AMC's funds have a real value — plus a
platform-wide summary strip.

Compliance boundary (binding): this endpoint reports DATA COVERAGE only — row
counts and percentages of how populated the catalog is. It never computes or
surfaces a fund score, rating, ranking, or any recommendation-adjacent number.

Data-freshness note: `covered_count` in every cell is a LIVE query against
`mf.mf_funds` / `mf.mf_fund_constituents` / `mf.fund_manager_history` — always
accurate as of the request. `mode`/`freq` (source classification) come from the
static `_SOURCE_CLASS` table below, which must be updated by hand whenever a new
scraper/manual pipeline is added — it is metadata/context only and never affects
the covered_count itself, so a stale entry here can't distort the real numbers.

Scheme-level grouping (confirmed 2026-07-08 — a founder-flagged 2.8% overall
completeness turned out to be a real denominator bug, not just a low number):
AMFI issues MANY plan-variant ISINs per scheme (Growth/IDCW-Daily/IDCW-Monthly/
Direct/Regular/...), but the enrichment pipeline (AUM/TER/riskometer/benchmark)
writes a value to only the ONE ISIN the resolver matched, never to its sibling
plan-variant ISINs of the same scheme (confirmed: HDFC Liquid Fund has 9
plan-variant ISINs, only 1 has aum_crore populated). Counting every ISIN as its
own "fund" therefore inflates the denominator ~2.6x relative to real distinct
schemes (14,910 ISIN rows vs 5,603 distinct (amc, scheme) pairs) and made the
metric look far harsher than the actual state of knowledge. `_SCHEME_KEY` below
groups by `mf_funds.fund_name_short` (the existing taxonomy-derived clean name
that already strips plan/option/frequency noise — see `mf/taxonomy.py::
derive_short_name`), falling back to the ISIN itself for the ~0.3% of rows with
no short name. A scheme now counts as "covered" for a field if ANY of its
plan-variant ISINs has that field populated.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import get_admin_db
from dhanradar.deps import RequireAdmin, UserContext
from dhanradar.models.mf import (
    MfFund,
    MfFundConstituent,
    MfFundManagerHistory,
    MfManualIngestFile,
)

from .amc_coverage_schemas import (
    FIELD_LABELS,
    FIELD_ORDER,
    AmcCoverageResponse,
    AmcCoverageRow,
    CoverageCell,
    CoverageField,
    CoverageMeta,
    CoverageSummary,
)

router = APIRouter(prefix="/admin/amc", tags=["admin-amc-coverage"])

NFO_WINDOW_DAYS = 180

# ---------------------------------------------------------------------------
# Short display-name overrides (founder spec: "first word(s)", e.g. "HDFC",
# "ICICI Pru", "ABSL"). Any `amc_name` not listed here falls back to its own
# first word — update this map when a new AMC is onboarded if the first-word
# fallback reads oddly.
# ---------------------------------------------------------------------------
_SHORT_NAME_OVERRIDES: dict[str, str] = {
    "ICICI Prudential Asset Management Company Limited": "ICICI Pru",
    "Nippon Life India Asset Management Limited": "Nippon",
    "UTI Asset Mgmt. Co. Ltd.": "UTI",
    "Kotak Mahindra Asset Management Company Limited.": "Kotak",
    "HDFC Asset Management Company Limited": "HDFC",
    "SBI Funds Management Limited": "SBI",
    "Aditya Birla Sun Life AMC Limited": "ABSL",
    "Bandhan AMC Limited": "Bandhan",
    "Axis Asset Management Co. Ltd.": "Axis",
    "Tata Asset Management Limited": "Tata",
    "DSP Asset Managers Private Limited": "DSP",
    "Franklin Templeton Asset Management (India) Private Limited": "Franklin",
    "Edelweiss Asset Management Limited": "Edelweiss",
    "Sundaram Asset Management Company Ltd": "Sundaram",
    "HSBC Asset Management (India) Private Ltd.": "HSBC",
    "Mirae Asset Investment Managers (India) Pvt. Ltd": "Mirae",
    "Baroda BNP Paribas Asset Management India Private Limited": "Baroda BNP",
    "Invesco Asset Management (India) Private Limited": "Invesco",
    "LIC Mutual Fund Asset Management Limited": "LIC",
    "Groww Asset Management Limited": "Groww",
    "Motilal Oswal Asset Management Company Limited": "Motilal Oswal",
    "PGIM India Asset Management Private Limite": "PGIM",
    "JM Financial Asset Management Limited": "JM Financial",
    "Union Asset Management Company Private Limited": "Union",
    "Bank of India Investment Managers Private Limited": "BOI",
    "Canara Robeco Asset Management Company Limited": "Canara Robeco",
    "quant Money Managers Limited": "Quant",
    "Mahindra Manulife Investment Management Pvt Ltd": "Mahindra Manulife",
    "ITI Asset Management Limited": "ITI",
    "Bajaj Finserv Asset Management Limited": "Bajaj Finserv",
    "Navi AMC Limited": "Navi",
    "Sahara Asset Management Company Private Limited": "Sahara",
    "WhiteOak Capital Asset Management Limited": "WhiteOak",
    "Trust Asset Management Private Limited": "Trust",
    "Wealth Company Asset Management Holdings Private Limited": "Wealth Co",
    "360 ONE Asset Management Limited": "360 ONE",
    "Quantum Asset Management Company Private Limited": "Quantum",
    "Taurus Asset Management Company Limited": "Taurus",
    "Shriram Asset Management Co. Ltd.": "Shriram",
    "Helios Capital Asset Management (India) Pvt. Ltd.": "Helios",
    "Samco Asset Management Private Limited": "Samco",
    "PPFAS Asset Management Pvt. Ltd.": "PPFAS",
    "NJ Asset Management Private Limited": "NJ",
    "Zerodha Asset Management Private Limited": "Zerodha",
    "Abakkus Investment Managers Private Limited": "Abakkus",
    "Jio BlackRock Asset Management Private Limited": "Jio BlackRock",
    "Angel One Asset Management Company Limited": "Angel One",
    "Capitalmind Asset Management Private Limited": "Capitalmind",
    "IL&FS Infra Asset Management Limited": "IL&FS",
    "Old Bridge Asset Management Private Limited": "Old Bridge",
    "Unifi Asset Management Private Limited": "Unifi",
    "Choice AMC Private Limited": "Choice",
    "AlphaGrep Investment Management Private Limited": "AlphaGrep",
    "IIFCL Asset Management Co. Ltd.": "IIFCL",
}


def _short_name(amc_name: str) -> str:
    override = _SHORT_NAME_OVERRIDES.get(amc_name)
    if override:
        return override
    return amc_name.split()[0] if amc_name.split() else amc_name


# ---------------------------------------------------------------------------
# Source classification (mode/freq) per short AMC name × field — metadata only,
# see module docstring. Source of truth: AMC_DATA_COMPLETENESS.md's per-AMC
# coverage-class table + the scraper roots list in
# dhanradar.tasks.mf (mf_constituents_fetch). UPDATE THIS when a new scraper or
# manual-ingest AMC is onboarded — it is never derived automatically.
# Unlisted AMC/field combos default to ("-", "-") (no source yet).
# ---------------------------------------------------------------------------
_AUTO_MONTHLY = ("A", "M")
_MANUAL_MONTHLY = ("M", "M")
_MANUAL_ANNUAL = ("M", "Y")
_MANUAL_ONCE = ("M", "O")
_NONE = ("-", "-")

_SOURCE_CLASS: dict[str, dict[CoverageField, tuple[str, str]]] = {
    "Nippon": {"constituents": _AUTO_MONTHLY, "aum": _AUTO_MONTHLY, "manager": _AUTO_MONTHLY},
    "UTI": {"constituents": _AUTO_MONTHLY, "manager": _AUTO_MONTHLY},
    "Mirae": {"constituents": _AUTO_MONTHLY},
    "PPFAS": {"constituents": _AUTO_MONTHLY},
    "Kotak": {
        "constituents": _MANUAL_MONTHLY,
        "benchmark": _MANUAL_ANNUAL,
    },
    "Edelweiss": {"constituents": _MANUAL_MONTHLY, "aum": _MANUAL_MONTHLY},
    "HDFC": {"constituents": _MANUAL_MONTHLY, "aum": _MANUAL_MONTHLY},
    "Axis": {"constituents": _MANUAL_MONTHLY, "aum": _MANUAL_MONTHLY, "manager": _MANUAL_MONTHLY},
    "ICICI Pru": {
        "constituents": _MANUAL_MONTHLY,
        "riskometer": _MANUAL_ANNUAL,
        "benchmark": _MANUAL_ANNUAL,
    },
    "SBI": {
        "constituents": _MANUAL_MONTHLY,
        "aum": _MANUAL_MONTHLY,
        "benchmark": _MANUAL_MONTHLY,
        "manager": _MANUAL_MONTHLY,
        "riskometer": _MANUAL_MONTHLY,
        "ter": _MANUAL_MONTHLY,
    },
    "ABSL": {"constituents": _MANUAL_MONTHLY},
    "DSP": {"ter": _MANUAL_ONCE},
    "Franklin": {"ter": _MANUAL_ONCE},
    "HSBC": {},  # staged locally, not yet uploaded — see BLOCKERS.md B82
}


def _class_for(short: str, field: CoverageField) -> tuple[str, str]:
    return _SOURCE_CLASS.get(short, {}).get(field, _NONE)


# A scheme group key: the taxonomy-derived clean name (already strips
# plan/option/frequency noise so Growth/IDCW-Daily/Direct/Regular ISINs of the
# SAME scheme collapse together), falling back to the ISIN for the rare row
# with no derived short name — never groups two DIFFERENT schemes together,
# only variants of the same one.
_SCHEME_KEY = func.coalesce(MfFund.fund_name_short, MfFund.isin)


async def _covered_by_amc(db: AsyncSession, predicate) -> dict[str, int]:
    """count(DISTINCT scheme) of rows in mf_funds matching `predicate`, grouped by
    amc_name — a scheme counts once even if only one of its plan-variant ISINs
    satisfies the predicate (see _SCHEME_KEY / module docstring)."""
    stmt = (
        select(MfFund.amc_name, func.count(func.distinct(_SCHEME_KEY)))
        .where(predicate)
        .group_by(MfFund.amc_name)
    )
    result = await db.execute(stmt)
    return {row[0]: row[1] for row in result.all() if row[0]}


@router.get("/coverage", response_model=AmcCoverageResponse)
async def get_amc_coverage(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
) -> AmcCoverageResponse:
    now = datetime.now(UTC)
    today = now.date()
    nfo_cutoff = today - timedelta(days=NFO_WINDOW_DAYS)

    # Distinct schemes per AMC (also gives total_funds / total_amcs) — deduped by
    # _SCHEME_KEY, NOT a raw ISIN-row count (see module docstring).
    funds_stmt = select(MfFund.amc_name, func.count(func.distinct(_SCHEME_KEY))).group_by(
        MfFund.amc_name
    )
    funds_by_amc: dict[str, int] = {
        row[0]: row[1] for row in (await db.execute(funds_stmt)).all() if row[0]
    }
    total_funds = sum(funds_by_amc.values())
    total_amcs = len(funds_by_amc)

    # NFO count (platform-wide — launch_date within the trailing window),
    # deduped by scheme so a brand-new scheme's Direct+Regular ISINs don't
    # double-count as 2 NFOs.
    nfo_count = (
        await db.execute(
            select(func.count(func.distinct(_SCHEME_KEY))).where(
                MfFund.launch_date.is_not(None), MfFund.launch_date >= nfo_cutoff
            )
        )
    ).scalar_one()

    # Per-field covered counts, grouped by amc_name.
    aum_by_amc = await _covered_by_amc(db, MfFund.aum_crore.is_not(None))
    ter_by_amc = await _covered_by_amc(db, MfFund.expense_ratio_pct.is_not(None))
    risk_by_amc = await _covered_by_amc(db, MfFund.risk_o_meter.is_not(None))
    bench_by_amc = await _covered_by_amc(db, MfFund.benchmark_index.is_not(None))
    exit_by_amc = await _covered_by_amc(
        db, (MfFund.exit_load_pct.is_not(None)) | (MfFund.exit_load_days.is_not(None))
    )

    # Constituents: distinct SCHEME with >=1 sibling ISIN having a constituent row,
    # grouped by amc_name (see _SCHEME_KEY / module docstring).
    constituents_stmt = (
        select(MfFund.amc_name, func.count(func.distinct(_SCHEME_KEY)))
        .join(MfFundConstituent, MfFundConstituent.isin == MfFund.isin)
        .group_by(MfFund.amc_name)
    )
    constituents_by_amc = {
        row[0]: row[1] for row in (await db.execute(constituents_stmt)).all() if row[0]
    }

    # Manager: distinct SCHEME with >=1 sibling ISIN having a CURRENT
    # (end_date IS NULL) manager row, grouped by amc_name.
    manager_stmt = (
        select(MfFund.amc_name, func.count(func.distinct(_SCHEME_KEY)))
        .join(MfFundManagerHistory, MfFundManagerHistory.scheme_uid == MfFund.isin)
        .where(MfFundManagerHistory.end_date.is_(None))
        .group_by(MfFund.amc_name)
    )
    manager_by_amc = {row[0]: row[1] for row in (await db.execute(manager_stmt)).all() if row[0]}

    field_counts: dict[CoverageField, dict[str, int]] = {
        "constituents": constituents_by_amc,
        "aum": aum_by_amc,
        "ter": ter_by_amc,
        "riskometer": risk_by_amc,
        "benchmark": bench_by_amc,
        "manager": manager_by_amc,
        "exit_load": exit_by_amc,
    }

    # Ingestion accuracy (platform-wide, manual-ingest inbox): parsed / (parsed + failed).
    parsed_count = (
        await db.execute(select(func.count()).where(MfManualIngestFile.status == "parsed"))
    ).scalar_one()
    failed_count = (
        await db.execute(select(func.count()).where(MfManualIngestFile.status == "failed"))
    ).scalar_one()
    accuracy_pct = (
        round(100.0 * parsed_count / (parsed_count + failed_count), 1)
        if (parsed_count + failed_count) > 0
        else 0.0
    )

    rows: list[AmcCoverageRow] = []
    weighted_completeness_sum = 0.0
    for amc_name, fund_count in sorted(funds_by_amc.items(), key=lambda kv: -kv[1]):
        short = _short_name(amc_name)
        fields: dict[CoverageField, CoverageCell] = {}
        fraction_sum = 0.0
        for field in FIELD_ORDER:
            covered = field_counts[field].get(amc_name, 0)
            mode, freq = _class_for(short, field)
            fields[field] = CoverageCell(covered_count=covered, mode=mode, freq=freq)  # type: ignore[arg-type]
            fraction_sum += (covered / fund_count) if fund_count else 0.0
        completeness_pct = round(100.0 * fraction_sum / len(FIELD_ORDER), 1)
        weighted_completeness_sum += completeness_pct * fund_count
        rows.append(
            AmcCoverageRow(
                amc_name=amc_name,
                short_name=short,
                fund_count=fund_count,
                fields=fields,
                completeness_pct=completeness_pct,
            )
        )

    overall_completeness_pct = (
        round(weighted_completeness_sum / total_funds, 1) if total_funds else 0.0
    )

    summary = CoverageSummary(
        total_amcs=total_amcs,
        total_funds=total_funds,
        nfo_count=int(nfo_count or 0),
        accuracy_pct=accuracy_pct,
        overall_completeness_pct=overall_completeness_pct,
        as_of=now.isoformat(),
    )

    return AmcCoverageResponse(
        summary=summary,
        rows=rows,
        meta=CoverageMeta(field_labels=FIELD_LABELS, field_order=list(FIELD_ORDER)),
    )
