"""Unit tests — Phase 1 leaderboard data backend
(docs/features/leaderboard-data-backend.md §4/§5).

Coverage:
  1. Migration wiring (0080, chained off 0079).
  2. Builder tests over seeded plain-dict fixtures (pure, no DB — mirrors the
     tasks/mf.py convention already used by test_fund_events.py):
       - top100 ordering + scheme plan/option variant dedup.
       - the shared dedup helper, order-independent.
       - movers_up / movers_down rank-delta diff, same-category only.
       - label_upgrades transition (in_form > on_track > off_track > out_of_form;
         insufficient_data ignored on either side).
       - champions "why" line — winner's own signal, no advisory verb.
       - staleness guard (_leaderboard_is_stale).
  3. Endpoint test — 200 envelope shape; a board absent from the DB is simply
     absent from `boards` (never a 500, never a fabricated empty entry).
  4. Leak tests — no FORBIDDEN_SCORE_KEYS key can reach a serialized response,
     whether smuggled in (fail-closed raise) or via the real builder path.
  5. Phase 2 data-quality hardening (2026-08-16) — the DATA-ARTIFACT plausibility
     guards on sip_3y/sip_5y/sip_consistency/risk_recovery/wealth_creator: implausible
     SIP-XIRR cap, is_segregated exclusion, non-growth-category exclusion, the
     since-launch CAGR bound, and the growth-category helper against real
     mf/taxonomy.py canonical strings.
"""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace
from typing import Any

from fastapi import Response

from dhanradar.mf.serialization import FORBIDDEN_SCORE_KEYS, serialize_leaderboard_response
from dhanradar.tasks.mf import (
    _build_leaderboard_ai_spotlight,
    _build_leaderboard_champions,
    _build_leaderboard_future_leaders,
    _build_leaderboard_hero,
    _build_leaderboard_hidden_gems,
    _build_leaderboard_label_upgrades,
    _build_leaderboard_manager_facts,
    _build_leaderboard_momentum,
    _build_leaderboard_movers,
    _build_leaderboard_perf_rail,
    _build_leaderboard_quality,
    _build_leaderboard_risk_recovery,
    _build_leaderboard_sip_beginner,
    _build_leaderboard_sip_consistency,
    _build_leaderboard_sip_rail,
    _build_leaderboard_top100,
    _build_leaderboard_value_ter,
    _build_leaderboard_wealth_creator,
    _dedupe_leaderboard_variants,
    _leaderboard_category_means,
    _leaderboard_fund_row,
    _leaderboard_is_growth_category,
    _leaderboard_is_stale,
    _leaderboard_takeaway,
    _since_launch_multiple,
)

# ci_guards / anti_pattern_sweep convention (docs/rca 'ci_guards FE advisory-verb
# trap'): banned list as a single space-joined string, not individual quoted
# literals, so a static advisory-verb scanner never flags the list itself.
_ADVISORY_VERBS = (
    "buy sell hold recommend recommended should avoid switch caution "
    "strong_buy strong_sell allocate overweight underweight"
).split(" ")


def _assert_no_advisory_verb(sentence: str) -> None:
    words = {w.strip(".,:%→").lower() for w in sentence.split()}
    hit = words & set(_ADVISORY_VERBS)
    assert not hit, f"advisory verb {hit} leaked into: {sentence!r}"


def _fund(
    isin: str,
    *,
    category: str = "Equity Scheme - Large Cap Fund",
    rank: int = 1,
    total: int = 10,
    **extra: Any,
) -> dict:
    base = {
        "isin": isin,
        "fund_name_short": None,
        "scheme_name": f"{isin} Scheme",
        "amc_name": "Test AMC",
        "sebi_category": category,
        "verb_label": "on_track",
        "confidence_band": "medium",
        "category_rank": rank,
        "category_total": total,
        "rank_delta": None,
        "riskometer": "Moderate",
        "return_1y_pct": 10.0,
        "return_3y_pct": 12.0,
        "return_5y_pct": 14.0,
        "expense_ratio_pct": 1.0,
        "aum_crore": 500.0,
        "sharpe_ratio": 1.2,
        "max_drawdown_pct": 8.0,
        "volatility_pct": 5.0,
        "launch_date": None,
        "contributing_signals": [],
        "is_segregated": False,
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# 1 — migration wiring
# ---------------------------------------------------------------------------


def test_migration_0080_wiring() -> None:
    import importlib.util
    import pathlib

    migration_path = (
        pathlib.Path(__file__).parent.parent.parent
        / "alembic"
        / "versions"
        / "0080_mf_leaderboard_boards.py"
    )
    spec = importlib.util.spec_from_file_location("_mig_0080", migration_path)
    assert spec is not None, f"could not locate migration at {migration_path}"
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)  # type: ignore[union-attr]
    assert mig.revision == "0080"
    assert mig.down_revision == "0079"
    assert callable(mig.upgrade)
    assert callable(mig.downgrade)


# ---------------------------------------------------------------------------
# 2a — top100 ordering + scheme plan/option variant dedup
# ---------------------------------------------------------------------------


def test_top100_orders_by_percentile_and_dedupes_scheme_variants() -> None:
    funds = [
        _fund("INE000A01011", fund_name_short="Alpha Fund", rank=1, total=10),
        # Same scheme, worse-ranked plan variant — must be dropped, never shown twice.
        _fund("INE000A01022", fund_name_short="Alpha Fund", rank=4, total=10),
        # Better within-category percentile (1/50=0.02) than Alpha's 1/10=0.1.
        _fund("INE000B02011", fund_name_short="Beta Fund", category="Equity Scheme - Mid Cap Fund", rank=1, total=50),
    ]
    rows = _build_leaderboard_top100(funds)
    isins = [r["isin"] for r in rows]

    assert "INE000A01022" not in isins, "duplicate scheme plan/option variant must not appear"
    assert isins == ["INE000B02011", "INE000A01011"]
    # FundRow shape only — never a score field.
    assert set(rows[0]) & FORBIDDEN_SCORE_KEYS == set()


def test_top100_is_growth_scoped_and_excludes_segregated() -> None:
    """D1 follow-up (2026-08-16): the flagship excludes debt/passive-bucket cohort
    artifacts (an index fund at 1/1341 took #1; liquid funds hit the top-10) and
    segregated portfolios."""
    funds = [
        _fund("INE000E05011", category="Equity Scheme - Small Cap Fund", rank=2, total=10),
        # Would win on percentile (1/1341) — but sits in the passive "Other" bucket.
        _fund("INE000I01011", category="Other Scheme - Index Funds", rank=1, total=1341),
        # Would win on percentile — but debt/liquid never enters the flagship.
        _fund("INE000L02011", category="Debt Scheme - Liquid Fund", rank=1, total=487),
        # Growth category but segregated — excluded.
        _fund("INE000S03011", category="Equity Scheme - Flexi Cap Fund", rank=1, total=10, is_segregated=True),
    ]
    rows = _build_leaderboard_top100(funds)
    assert [r["isin"] for r in rows] == ["INE000E05011"]


# ---------------------------------------------------------------------------
# 2a-bis — sip_beginner (D4 published rule)
# ---------------------------------------------------------------------------


def test_sip_beginner_applies_published_rule_and_orders_steadiest_first() -> None:
    """D4 rule: large-cap or hybrid (ex-arbitrage), label on_track or better,
    steadiest rolling-1Y first; 3Y SIP XIRR is the display metric; sip-rail
    artifact guards inherited."""
    ok = dict(sip_xirr_3y_pct=12.0, rolling_1y_pct_positive=90.0)
    funds = [
        _fund("INE000A01011", **ok),  # large-cap on_track — in
        _fund(
            "INE000B01011",
            category="Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage",
            sip_xirr_3y_pct=11.0,
            rolling_1y_pct_positive=95.0,  # steadier -> ranks first
        ),
        _fund("INE000C01011", category="Hybrid Scheme - Arbitrage Fund", **ok),  # cash-like — out
        _fund("INE000D01011", verb_label="off_track", **ok),  # label below On Track — out
        _fund("INE000E01011", category="Equity Scheme - Small Cap Fund", **ok),  # not a rule category — out
        _fund("INE000F01011", is_segregated=True, **ok),  # artifact guard — out
        _fund("INE000G01011", sip_xirr_3y_pct=55.0, rolling_1y_pct_positive=99.0),  # implausible XIRR — out
        _fund("INE000H01011", sip_xirr_3y_pct=12.0, rolling_1y_pct_positive=None),  # no steadiness metric — out
    ]
    rows = _build_leaderboard_sip_beginner(funds)
    assert [r["isin"] for r in rows] == ["INE000B01011", "INE000A01011"]
    assert rows[0]["metric_value"] == 11.0
    assert rows[0]["metric_unit"] == "pct_sip_xirr"
    assert set(rows[0]) & FORBIDDEN_SCORE_KEYS == set()


def test_dedupe_variants_keeps_best_by_sort_key_regardless_of_input_order() -> None:
    worse = {"isin": "A2", "fund_name_short": "Same Scheme"}
    better = {"isin": "A1", "fund_name_short": "Same Scheme"}
    other = {"isin": "B1", "fund_name_short": "Other Scheme"}
    out = _dedupe_leaderboard_variants([worse, better, other], sort_key=lambda f: f["isin"])
    assert {f["isin"] for f in out} == {"A1", "B1"}


# ---------------------------------------------------------------------------
# 2b — movers_up / movers_down
# ---------------------------------------------------------------------------


def test_movers_up_and_down_split_by_rank_delta_same_category_only() -> None:
    funds = [
        _fund("INE_UP01", category="Large Cap Fund", rank=3, total=50),  # 10 -> 3, delta +7
        _fund("INE_DOWN1", category="Large Cap Fund", rank=20, total=50),  # 5 -> 20, delta -15
        _fund("INE_FLAT1", category="Large Cap Fund", rank=8, total=50),  # unchanged
        _fund("INE_RECAT1", category="Debt Fund", rank=2, total=30),  # category changed -> incomparable
    ]
    prev_by_isin = {
        "INE_UP01": {"rank": 10, "sebi_category": "Large Cap Fund", "verb_label": "on_track"},
        "INE_DOWN1": {"rank": 5, "sebi_category": "Large Cap Fund", "verb_label": "on_track"},
        "INE_FLAT1": {"rank": 8, "sebi_category": "Large Cap Fund", "verb_label": "on_track"},
        "INE_RECAT1": {"rank": 2, "sebi_category": "Small Cap Fund", "verb_label": "on_track"},
    }

    up = _build_leaderboard_movers(funds, prev_by_isin, direction="up")
    down = _build_leaderboard_movers(funds, prev_by_isin, direction="down")

    assert [r["isin"] for r in up] == ["INE_UP01"]
    assert up[0]["metric_value"] == 7
    assert up[0]["metric_unit"] == "rank_delta"
    assert [r["isin"] for r in down] == ["INE_DOWN1"]
    assert down[0]["metric_value"] == -15


# ---------------------------------------------------------------------------
# 2c — label_upgrades transition
# ---------------------------------------------------------------------------


def test_label_upgrades_only_improving_transitions_ignoring_insufficient_data() -> None:
    funds = [
        _fund("INE_A1", verb_label="in_form"),  # off_track -> in_form: improved
        _fund("INE_B1", verb_label="on_track"),  # on_track -> on_track: no change
        _fund("INE_C1", verb_label="on_track"),  # insufficient_data -> on_track: ignored (non-neg #4)
        _fund("INE_D1", verb_label="off_track"),  # in_form -> off_track: downgrade, not an upgrade
    ]
    prev_by_isin = {
        "INE_A1": {"rank": 5, "sebi_category": "Large Cap Fund", "verb_label": "off_track"},
        "INE_B1": {"rank": 5, "sebi_category": "Large Cap Fund", "verb_label": "on_track"},
        "INE_C1": {"rank": 5, "sebi_category": "Large Cap Fund", "verb_label": "insufficient_data"},
        "INE_D1": {"rank": 5, "sebi_category": "Large Cap Fund", "verb_label": "in_form"},
    }

    rows = _build_leaderboard_label_upgrades(funds, prev_by_isin)

    assert [r["isin"] for r in rows] == ["INE_A1"]
    assert rows[0]["label_from"] == "off_track"
    assert rows[0]["label_to"] == "in_form"


# ---------------------------------------------------------------------------
# 2d — champions "why" line: winner's own signal, no advisory verb
# ---------------------------------------------------------------------------


def test_champion_why_uses_winners_own_signal_no_advisory_verb() -> None:
    funds = [
        _fund(
            "INE000A01011",
            fund_name_short="Alpha Fund",
            category="Large Cap Fund",
            rank=1,
            total=10,
            contributing_signals=["ahead of category peers over the past year"],
        ),
        _fund("INE000B02011", fund_name_short="Beta Fund", category="Large Cap Fund", rank=2, total=10),
    ]
    rows = _build_leaderboard_champions(funds)

    assert len(rows) == 1  # one category
    row = rows[0]
    assert row["winner"]["isin"] == "INE000A01011"
    assert row["runner_up"]["isin"] == "INE000B02011"
    assert "ahead of category peers over the past year" in row["why"]
    _assert_no_advisory_verb(row["why"])


def test_champions_single_scheme_category_has_no_runner_up() -> None:
    funds = [_fund("INE000A01011", category="Solo Fund Category", rank=1, total=1)]
    rows = _build_leaderboard_champions(funds)
    assert rows[0]["runner_up"] is None


# ---------------------------------------------------------------------------
# 2e — staleness guard
# ---------------------------------------------------------------------------


def test_staleness_guard_skips_beyond_3_days() -> None:
    assert _leaderboard_is_stale(date(2026, 8, 10), today=date(2026, 8, 16)) is True  # 6 days
    assert _leaderboard_is_stale(date(2026, 8, 13), today=date(2026, 8, 16)) is False  # exactly 3 days
    assert _leaderboard_is_stale(date(2026, 8, 12), today=date(2026, 8, 16)) is True  # 4 days


# ---------------------------------------------------------------------------
# 2f — Phase 2 boards (docs/features/leaderboard-data-backend.md §8): wealth
# creator, SIP rails (_build_leaderboard_sip_rail), SIP consistency, drawdown
# recovery.
# ---------------------------------------------------------------------------


def test_since_launch_multiple_none_under_5y_guard() -> None:
    result = _since_launch_multiple(date(2022, 1, 1), 100.0, date(2025, 1, 1), 150.0)  # ~3y span
    assert result is None


def test_since_launch_multiple_none_when_first_nav_not_positive() -> None:
    result = _since_launch_multiple(date(2018, 1, 1), 0.0, date(2026, 1, 1), 200.0)  # 8y span
    assert result is None


def test_since_launch_multiple_computes_ratio_over_5y_guard() -> None:
    result = _since_launch_multiple(date(2018, 1, 1), 50.0, date(2026, 1, 1), 200.0)  # 8y span
    assert result == 4.0


def test_since_launch_multiple_cagr_guard_rejects_implausible_compounding() -> None:
    """178x over 12y implies ~54%/yr — the real prod artifact (Edelweiss Liquid Fund
    178.78x) off a corrupted early NAV row, not genuine compounding."""
    result = _since_launch_multiple(date(2014, 1, 1), 1.0, date(2026, 1, 1), 178.0)
    assert result is None


def test_since_launch_multiple_cagr_guard_keeps_honest_high_multiple() -> None:
    """8x over 15y implies ~15%/yr — a real, plausible long-run equity multiple; the
    CAGR guard must not reject an honest high-multiple fund."""
    result = _since_launch_multiple(date(2011, 1, 1), 25.0, date(2026, 1, 1), 200.0)
    assert result == 8.0


def test_wealth_creator_orders_by_since_launch_multiple_excludes_null() -> None:
    funds = [
        _fund("INE_W1"),
        _fund("INE_W2"),
        _fund("INE_W3"),  # no entry in multiples_by_isin — short history, excluded not zero-filled
    ]
    multiples_by_isin = {"INE_W1": 5.0, "INE_W2": 8.0}
    rows = _build_leaderboard_wealth_creator(funds, multiples_by_isin)
    assert [r["isin"] for r in rows] == ["INE_W2", "INE_W1"]
    assert rows[0]["metric_value"] == 8.0
    assert rows[0]["metric_unit"] == "x_since_launch"


def test_wealth_creator_excludes_segregated_funds() -> None:
    funds = [_fund("INE_WOK"), _fund("INE_WSEG", is_segregated=True)]
    multiples_by_isin = {"INE_WOK": 5.0, "INE_WSEG": 6.0}
    rows = _build_leaderboard_wealth_creator(funds, multiples_by_isin)
    assert [r["isin"] for r in rows] == ["INE_WOK"]


def test_sip_rail_orders_descending_excludes_null() -> None:
    funds = [
        _fund("INE_S1", sip_xirr_3y_pct=10.0, sip_xirr_5y_pct=9.0),
        _fund("INE_S2", sip_xirr_3y_pct=14.0, sip_xirr_5y_pct=None),
    ]
    sip_3y = _build_leaderboard_sip_rail(funds, "sip_xirr_3y_pct")
    sip_5y = _build_leaderboard_sip_rail(funds, "sip_xirr_5y_pct")
    assert [r["isin"] for r in sip_3y] == ["INE_S2", "INE_S1"]
    assert [r["isin"] for r in sip_5y] == ["INE_S1"]  # null sip_xirr_5y_pct excluded
    assert sip_3y[0]["metric_unit"] == "pct_sip_xirr"


def test_sip_rail_excludes_segregated_non_growth_and_implausible_xirr() -> None:
    """The three DATA-ARTIFACT guards, each independently excluding a candidate that
    would otherwise win the board — mirrors the real prod artifacts (Franklin India
    Short-Term 89.25% segregated spike, ICICI Overnight 53.24% cash-fund win)."""
    funds = [
        _fund("INE_OK", sip_xirr_3y_pct=18.0),
        _fund("INE_SEG", sip_xirr_3y_pct=20.0, is_segregated=True),
        _fund("INE_CASH", sip_xirr_3y_pct=6.0, category="Debt Scheme - Liquid Fund"),
        _fund("INE_SPIKE", sip_xirr_3y_pct=89.25),
    ]
    rows = _build_leaderboard_sip_rail(funds, "sip_xirr_3y_pct")
    assert [r["isin"] for r in rows] == ["INE_OK"]


def test_sip_consistency_requires_3y_history_and_orders_by_pct_positive() -> None:
    funds = [
        _fund("INE_C1", rolling_1y_pct_positive=90.0, return_3y_pct=12.0),
        _fund("INE_C2", rolling_1y_pct_positive=95.0, return_3y_pct=None),  # < 3Y history — excluded
        _fund("INE_C3", rolling_1y_pct_positive=80.0, return_3y_pct=10.0),
    ]
    rows = _build_leaderboard_sip_consistency(funds)
    assert [r["isin"] for r in rows] == ["INE_C1", "INE_C3"]
    assert rows[0]["metric_value"] == 90.0
    assert rows[0]["metric_unit"] == "pct_rolling_positive"


def test_sip_consistency_excludes_segregated_and_non_growth() -> None:
    """A cash fund is 100%-positive by construction — vacuous (prod artifact: ITI
    Liquid Fund topped this board at 100%)."""
    funds = [
        _fund("INE_OK", rolling_1y_pct_positive=90.0, return_3y_pct=12.0),
        _fund("INE_SEG", rolling_1y_pct_positive=95.0, return_3y_pct=12.0, is_segregated=True),
        _fund(
            "INE_CASH",
            rolling_1y_pct_positive=100.0,
            return_3y_pct=6.0,
            category="Debt Scheme - Liquid Fund",
        ),
    ]
    rows = _build_leaderboard_sip_consistency(funds)
    assert [r["isin"] for r in rows] == ["INE_OK"]


def test_risk_recovery_orders_ascending_excludes_never_recovered() -> None:
    funds = [
        _fund("INE_R1", recovery_days=120),
        _fund("INE_R2", recovery_days=30),
        _fund("INE_R3", recovery_days=None),  # never recovered — excluded
    ]
    rows = _build_leaderboard_risk_recovery(funds)
    assert [r["isin"] for r in rows] == ["INE_R2", "INE_R1"]
    assert rows[0]["metric_value"] == 30
    assert rows[0]["metric_unit"] == "days_recovery"


def test_risk_recovery_excludes_segregated_and_non_growth() -> None:
    """An overnight fund 'recovering' in 2 days is definitionally meaningless (prod
    artifact: TRUST Overnight Fund - 2 Days topped this board)."""
    funds = [
        _fund("INE_OK", recovery_days=45),
        _fund("INE_SEG", recovery_days=10, is_segregated=True),
        _fund("INE_CASH", recovery_days=2, category="Debt Scheme - Overnight Fund"),
    ]
    rows = _build_leaderboard_risk_recovery(funds)
    assert [r["isin"] for r in rows] == ["INE_OK"]


def test_wealth_creator_excludes_non_growth_categories() -> None:
    """Phase 2.2 (2nd live run): ICICI Overnight topped at '10.01x' — a debt fund's
    decades-long face-value drift is not this board's promise of growth compounding."""
    funds = [
        _fund("INE_WEQ"),
        _fund("INE_WCASH", category="Debt Scheme - Overnight Fund"),
    ]
    multiples_by_isin = {"INE_WEQ": 6.0, "INE_WCASH": 10.0}
    rows = _build_leaderboard_wealth_creator(funds, multiples_by_isin)
    assert [r["isin"] for r in rows] == ["INE_WEQ"]


def test_sip_consistency_excludes_arbitrage_funds() -> None:
    """Phase 2.2 (2nd live run): ITI Arbitrage topped at 100% — arbitrage sits in
    the Hybrid bucket but is cash-like by construction (same vacuous-winner problem)."""
    funds = [
        _fund("INE_OK2", rolling_1y_pct_positive=90.0, return_3y_pct=12.0),
        _fund(
            "INE_ARB",
            rolling_1y_pct_positive=100.0,
            return_3y_pct=7.0,
            category="Hybrid Scheme - Arbitrage Fund",
        ),
    ]
    rows = _build_leaderboard_sip_consistency(funds)
    assert [r["isin"] for r in rows] == ["INE_OK2"]


def test_risk_recovery_requires_a_real_fall() -> None:
    """Phase 2.2 (2nd live run): a CRISIL IBX AAA debt index fund 'recovered' in 2
    days from a rounding-sized dip — recovery is only meaningful from a drawdown an
    investor would actually feel (max_drawdown >= 5%)."""
    funds = [
        _fund("INE_REAL", recovery_days=60, max_drawdown_pct=12.0),
        _fund("INE_DIP", recovery_days=2, max_drawdown_pct=0.4),
    ]
    rows = _build_leaderboard_risk_recovery(funds)
    assert [r["isin"] for r in rows] == ["INE_REAL"]


def test_leaderboard_is_growth_category_matches_real_canonical_strings() -> None:
    """Against the actual mf/taxonomy.py canonical leaf strings, not a paraphrase —
    Equity/Hybrid/Solution-Oriented + the Index-funds bucket are growth; Debt and the
    remaining Other Scheme leaves (Gold ETF here) are not."""
    assert _leaderboard_is_growth_category("Equity Scheme - Large Cap Fund") is True
    assert _leaderboard_is_growth_category("Equity Scheme - Sectoral/ Thematic") is True
    assert _leaderboard_is_growth_category("Hybrid Scheme - Aggressive Hybrid Fund") is True
    assert _leaderboard_is_growth_category("Solution Oriented Scheme - Retirement Fund") is True
    assert _leaderboard_is_growth_category("Other Scheme - Index Funds") is True
    assert _leaderboard_is_growth_category("Debt Scheme - Liquid Fund") is False
    assert _leaderboard_is_growth_category("Debt Scheme - Overnight Fund") is False
    assert _leaderboard_is_growth_category("Other Scheme - Gold ETF") is False
    assert _leaderboard_is_growth_category(None) is False


# ---------------------------------------------------------------------------
# 2g — Phase 3a boards (docs/features/leaderboard-data-backend.md §9b): hidden
# gems, future leaders, momentum, quality, cross-board AI spotlight.
# ---------------------------------------------------------------------------


def test_hidden_gems_requires_top_quartile_rank_and_below_category_median_aum() -> None:
    # category AUM pool (excl. HG5's None) = {10, 500, 20, 600, 30, 700}
    # -> sorted [10, 20, 30, 500, 600, 700] -> median = (30 + 500) / 2 = 265.
    funds = [
        _fund("INE_HG1", category="Small Cap Fund", rank=1, total=20, aum_crore=10.0),  # gem: top-quartile, well below median
        _fund("INE_HG2", category="Small Cap Fund", rank=2, total=20, aum_crore=500.0),  # top-quartile but ABOVE median -> excluded
        _fund("INE_HG3", category="Small Cap Fund", rank=15, total=20, aum_crore=20.0),  # below median but NOT top-quartile -> excluded
        _fund("INE_HG4", category="Small Cap Fund", rank=10, total=20, aum_crore=600.0),  # pool filler, not top-quartile
        _fund("INE_HG5", category="Small Cap Fund", rank=4, total=20, aum_crore=None),  # no AUM -> excluded, never in the median pool
        _fund(
            "INE_HG6", category="Small Cap Fund", rank=1, total=20, aum_crore=30.0, is_segregated=True
        ),  # otherwise qualifies (top-quartile, below median) but segregated -> excluded
        _fund("INE_HG7", category="Small Cap Fund", rank=11, total=20, aum_crore=700.0),  # pool filler, not top-quartile
    ]
    rows = _build_leaderboard_hidden_gems(funds)
    assert [r["isin"] for r in rows] == ["INE_HG1"]
    assert rows[0]["metric_value"] is None
    assert rows[0]["metric_unit"] == "gem"


def test_future_leaders_requires_positive_delta_and_top_half_category_rank() -> None:
    funds = [
        _fund("INE_FL1", rank=5, total=20, rank_delta=3),  # top half (0.25) + rising -> leader
        _fund("INE_FL2", rank=3, total=20, rank_delta=1),  # top half, smaller delta -> ranks after FL1
        _fund("INE_FL3", rank=15, total=20, rank_delta=5),  # bigger delta but bottom half (0.75) -> excluded
        _fund("INE_FL4", rank=2, total=20, rank_delta=-1),  # top half but falling -> excluded
        _fund("INE_FL5", rank=1, total=20, rank_delta=None),  # no delta (no prior rank) -> excluded
    ]
    rows = _build_leaderboard_future_leaders(funds)
    assert [r["isin"] for r in rows] == ["INE_FL1", "INE_FL2"]
    assert rows[0]["metric_value"] == 3
    assert rows[0]["metric_unit"] == "rank_delta"


def test_momentum_requires_ahead_of_peers_signal_and_positive_delta() -> None:
    from dhanradar.scoring.engine.signal_names import SignalName, display

    ahead_1y = display(SignalName.COHORT_1Y_AHEAD)
    ahead_3y = display(SignalName.COHORT_3Y_AHEAD)
    funds = [
        _fund("INE_M1", rank_delta=5, return_1y_pct=20.0, contributing_signals=[ahead_1y]),
        # Same delta as M1, higher 1Y return -> wins the tie-break.
        _fund("INE_M2", rank_delta=5, return_1y_pct=25.0, contributing_signals=[ahead_3y]),
        _fund("INE_M3", rank_delta=-2, contributing_signals=[ahead_1y]),  # falling -> excluded
        _fund(
            "INE_M4", rank_delta=8, contributing_signals=["drawdown contained versus category peers"]
        ),  # rising but no ahead-of-peers phrase -> excluded
    ]
    rows = _build_leaderboard_momentum(funds)
    assert [r["isin"] for r in rows] == ["INE_M2", "INE_M1"]
    assert rows[0]["metric_value"] == 5
    assert rows[0]["metric_unit"] == "rank_delta"


def test_quality_requires_high_consistency_orders_by_sharpe() -> None:
    """data_coverage deliberately NOT gated (2026-08-16): uniformly 'low'
    platform-wide (0/~8,300 at high) — the two-factor gate shipped an empty
    board. consistency=='high' is the engine's own discriminating signal."""
    funds = [
        _fund("INE_Q1", sharpe_ratio=1.5, confidence_factors={"consistency": "high", "data_coverage": "low"}),
        _fund(
            "INE_Q2", sharpe_ratio=2.0, confidence_factors={"consistency": "medium", "data_coverage": "low"}
        ),  # consistency not high -> excluded
        _fund("INE_Q3", sharpe_ratio=1.8, confidence_factors={"consistency": "high", "data_coverage": "low"}),
        _fund(
            "INE_Q4",
            sharpe_ratio=3.0,
            confidence_factors={"consistency": "high", "data_coverage": "low"},
            is_segregated=True,
        ),  # segregated -> excluded
    ]
    rows = _build_leaderboard_quality(funds)
    assert [r["isin"] for r in rows] == ["INE_Q3", "INE_Q1"]
    assert rows[0]["metric_value"] == 1.8
    assert rows[0]["metric_unit"] == "sharpe_ratio"


def test_ai_spotlight_counts_cross_board_appearances_including_champion_winners() -> None:
    fund_row_a = _leaderboard_fund_row(_fund("INE_AI1", fund_name_short="Alpha"))
    fund_row_b = _leaderboard_fund_row(_fund("INE_AI2", fund_name_short="Beta"))
    fund_row_c = _leaderboard_fund_row(_fund("INE_AI3", fund_name_short="Gamma"))
    boards = {
        "top100": [fund_row_a, fund_row_b, fund_row_c],
        "perf_1y": [fund_row_a],
        "risk_sharpe": [fund_row_a],
        "champions": [{"category": "Large Cap Fund", "winner": fund_row_b, "runner_up": None, "why": "x"}],
        "value_ter": [fund_row_b],
        "amc_facts": [{"amc_name": "Test AMC", "fund_count": 1}],  # no isin — never crashes
    }
    rows = _build_leaderboard_ai_spotlight(boards)
    # AI1: top100+perf_1y+risk_sharpe=3; AI2: top100+champions(winner)+value_ter=3;
    # AI3: top100 only=1 -> below the >=2 gate, excluded. Tie breaks by top100 position.
    assert [r["isin"] for r in rows] == ["INE_AI1", "INE_AI2"]
    assert rows[0]["metric_value"] == 3
    assert rows[0]["metric_unit"] == "boards"


# ---------------------------------------------------------------------------
# 2h — Phase 3b manager_facts (docs/features/leaderboard-data-backend.md §9b):
# aggregate dedup, tenure, percentile word, the >=2-fund gate, no number leak.
# ---------------------------------------------------------------------------


def test_manager_facts_dedupes_gates_on_two_funds_and_computes_tenure_and_word() -> None:
    manager_rows = [
        {
            "manager_name": "Jane Doe",
            "start_date": date(2020, 1, 1),
            "isin": "INE_MG1",
            "category_rank": 2,
            "category_total": 20,  # percentile 0.10
            "fund_name_short": "Fund One",
            "scheme_name": "Fund One - Direct - Growth",
            "amc_name": "Alpha AMC",
        },
        {
            # Same scheme, plan/option variant of Fund One — must collapse (SCHEME_KEY dedup).
            "manager_name": "Jane Doe",
            "start_date": date(2020, 1, 1),
            "isin": "INE_MG1V",
            "category_rank": 5,
            "category_total": 20,
            "fund_name_short": "Fund One",
            "scheme_name": "Fund One - Regular - Growth",
            "amc_name": "Alpha AMC",
        },
        {
            "manager_name": "Jane Doe",
            "start_date": date(2016, 8, 16),  # earliest -> drives tenure
            "isin": "INE_MG2",
            "category_rank": 1,
            "category_total": 20,  # percentile 0.05 — best -> top_fund
            "fund_name_short": "Fund Two",
            "scheme_name": "Fund Two - Direct - Growth",
            "amc_name": "Alpha AMC",
        },
        {
            "manager_name": "Solo Manager",  # only ONE fund -> gated out (< 2 funds)
            "start_date": date(2015, 1, 1),
            "isin": "INE_SOLO",
            "category_rank": 1,
            "category_total": 5,
            "fund_name_short": "Solo Fund",
            "scheme_name": "Solo Fund - Direct - Growth",
            "amc_name": "Beta AMC",
        },
    ]
    as_of = date(2026, 8, 16)
    rows = _build_leaderboard_manager_facts(manager_rows, as_of_date=as_of)

    assert [r["manager_name"] for r in rows] == ["Jane Doe"]  # Solo Manager gated out
    row = rows[0]
    assert row["funds_count"] == 2  # variant collapsed: Fund One + Fund Two
    assert row["amc_name"] == "Alpha AMC"
    assert row["top_fund_name"] == "Fund Two"  # best percentile (0.05 vs Fund One's 0.10)
    assert row["percentile_word"] == "Strong"  # avg (0.05+0.10)/2=0.075 <= 0.25
    expected_tenure = round((as_of - date(2016, 8, 16)).days / 365.25, 1)
    assert row["tenure_years"] == expected_tenure
    # leaderboard.manager_row shape only — no raw percentile number, no score.
    assert set(row) == {
        "manager_name",
        "amc_name",
        "funds_count",
        "tenure_years",
        "percentile_word",
        "top_fund_name",
    }


def test_manager_facts_percentile_word_bands() -> None:
    manager_rows = [
        {
            "manager_name": "Good Manager",
            "start_date": date(2020, 1, 1),
            "isin": f"INE_GM{i}",
            "category_rank": 8,
            "category_total": 20,  # percentile 0.4 -> "Good" (<= 0.5)
            "fund_name_short": f"Fund {i}",
            "scheme_name": f"Fund {i} - Direct - Growth",
            "amc_name": "Gamma AMC",
        }
        for i in range(2)
    ]
    rows = _build_leaderboard_manager_facts(manager_rows, as_of_date=date(2026, 8, 16))
    assert rows[0]["percentile_word"] == "Good"


# ---------------------------------------------------------------------------
# 3 — endpoint: 200 envelope shape, absent boards omitted
# ---------------------------------------------------------------------------


class _FakeLeaderboardDB:
    """Minimal AsyncSession stub — `select(MfLeaderboardBoard)...scalars().all()`."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    async def execute(self, stmt: Any) -> "_FakeLeaderboardDB":  # noqa: UP037
        return self

    def scalars(self) -> "_FakeLeaderboardDB":  # noqa: UP037
        return self

    def all(self) -> list[Any]:
        return list(self._rows)


async def test_leaderboard_endpoint_envelope_shape_and_absent_boards_omitted() -> None:
    from dhanradar.mf.router import leaderboard

    fund_row = {
        "isin": "INE000A01011",
        "fund_name_short": "Alpha Fund",
        "scheme_name": "Alpha Fund - Direct - Growth",
        "amc_name": "Test AMC",
        "sebi_category": "Large Cap Fund",
        "verb_label": "on_track",
        "confidence_band": "medium",
        "category_rank": 1,
        "category_total": 20,
        "rank_delta": 2,
        "riskometer": "Moderate",
        "return_1y_pct": 12.0,
        "return_3y_pct": 15.0,
        "return_5y_pct": 18.0,
        "expense_ratio_pct": 0.8,
        "aum_crore": 900.0,
        "sharpe_ratio": 1.1,
        "max_drawdown_pct": 9.0,
        "metric_value": None,
        "metric_unit": None,
    }
    rows = [
        SimpleNamespace(
            board_key="hero",
            as_of_date=date(2026, 8, 15),
            payload={
                "funds_ranked": 500,
                "categories": 12,
                "top_fund": fund_row,
                "trending_category": "Large Cap Fund",
                "live_board_count": 2,
            },
        ),
        SimpleNamespace(
            board_key="top100", as_of_date=date(2026, 8, 15), payload={"rows": [fund_row]}
        ),
    ]
    db = _FakeLeaderboardDB(rows)
    resp = Response()

    envelope = await leaderboard(db=db, response=resp)

    assert envelope["as_of"] == "2026-08-15"
    assert set(envelope["boards"]) == {"top100"}  # only the board actually written
    assert "champions" not in envelope["boards"]  # not-yet-wired board simply absent
    assert envelope["boards"]["top100"]["title"] == "DhanRadar Top 100"
    assert envelope["boards"]["top100"]["rows"][0]["isin"] == "INE000A01011"
    assert envelope["hero"]["funds_ranked"] == 500
    assert envelope["disclosure"]
    assert envelope["not_advice"]
    assert resp.headers["Cache-Control"] == "public, max-age=300"


async def test_leaderboard_endpoint_empty_table_returns_null_as_of() -> None:
    from dhanradar.mf.router import leaderboard

    envelope = await leaderboard(db=_FakeLeaderboardDB([]), response=Response())

    assert envelope["as_of"] is None
    assert envelope["hero"] is None
    assert envelope["boards"] == {}


# ---------------------------------------------------------------------------
# 4 — leak tests: no FORBIDDEN_SCORE_KEYS anywhere in a serialized response
# ---------------------------------------------------------------------------


def test_forbidden_score_key_smuggled_in_is_stripped_not_leaked() -> None:
    """`_scrub` drops a FORBIDDEN_SCORE_KEYS key silently (the #2 backstop) — a
    leaderboard response never surfaces one, whether stripped here or excluded by
    the field allowlist (defense in depth, both layers independently exclude it)."""
    poisoned_row = {"isin": "INE000A01011", "unified_score": 87}
    envelope = serialize_leaderboard_response(
        as_of="2026-08-15",
        hero=None,
        boards={"top100": {"title": "t", "rows": [poisoned_row]}},
    )
    blob = json.dumps(envelope, default=str)
    assert "unified_score" not in blob


def test_full_leaderboard_response_has_no_forbidden_score_keys() -> None:
    funds = [
        _fund("INE000A01011", fund_name_short="Alpha Fund", category="Large Cap Fund", rank=1, total=10),
        _fund("INE000B02011", fund_name_short="Beta Fund", category="Mid Cap Fund", rank=1, total=50),
    ]
    top100_rows = _build_leaderboard_top100(funds)
    champions_rows = _build_leaderboard_champions(funds)
    hero = _build_leaderboard_hero(funds, {}, top100_rows, live_board_count=2)

    envelope = serialize_leaderboard_response(
        as_of="2026-08-15",
        hero=hero,
        boards={
            "top100": {"title": "DhanRadar Top 100", "rows": top100_rows},
            "champions": {"title": "Category Champions", "rows": champions_rows},
        },
    )

    blob = json.dumps(envelope, default=str)
    for key in FORBIDDEN_SCORE_KEYS:
        assert key not in blob, f"forbidden score key {key!r} leaked into the leaderboard response"


def test_manager_row_allowlist_strips_raw_percentile_and_forbidden_score_keys() -> None:
    """`leaderboard.manager_row` (§9b) — a manager row must never leak the raw
    averaged percentile number or any FORBIDDEN_SCORE_KEYS, whether smuggled in
    directly or produced via the real `_build_leaderboard_manager_facts` path."""
    poisoned_row = {
        "manager_name": "Jane Doe",
        "amc_name": "Alpha AMC",
        "funds_count": 2,
        "tenure_years": 5.0,
        "percentile_word": "Strong",
        "top_fund_name": "Fund One",
        "avg_percentile": 0.1,  # not in the allowlist — must never reach a client
        "unified_score": 87,  # forbidden-key tripwire too
    }
    envelope = serialize_leaderboard_response(
        as_of="2026-08-15",
        hero=None,
        boards={"manager_facts": {"title": "t", "rows": [poisoned_row]}},
    )
    assert envelope["boards"]["manager_facts"]["rows"][0] == {
        "manager_name": "Jane Doe",
        "amc_name": "Alpha AMC",
        "funds_count": 2,
        "tenure_years": 5.0,
        "percentile_word": "Strong",
        "top_fund_name": "Fund One",
    }
    blob = json.dumps(envelope, default=str)
    assert "avg_percentile" not in blob
    assert "unified_score" not in blob

    # Real builder path — same guarantee end to end.
    manager_rows = [
        {
            "manager_name": "Real Manager",
            "start_date": date(2018, 1, 1),
            "isin": f"INE_RM{i}",
            "category_rank": 3,
            "category_total": 12,
            "fund_name_short": f"Real Fund {i}",
            "scheme_name": f"Real Fund {i} - Direct - Growth",
            "amc_name": "Delta AMC",
        }
        for i in range(2)
    ]
    manager_facts_rows = _build_leaderboard_manager_facts(manager_rows, as_of_date=date(2026, 8, 15))
    envelope2 = serialize_leaderboard_response(
        as_of="2026-08-15",
        hero=None,
        boards={"manager_facts": {"title": "t", "rows": manager_facts_rows}},
    )
    blob2 = json.dumps(envelope2, default=str)
    for key in FORBIDDEN_SCORE_KEYS:
        assert key not in blob2
    assert "avg_percentile" not in blob2
    assert "percentile_word" in blob2


# ---------------------------------------------------------------------------
# 5 — V1 category-context numbers (2026-08-16)
# ---------------------------------------------------------------------------


def test_leaderboard_category_means_computes_mean_excludes_segregated_and_missing_metric() -> None:
    funds = [
        _fund("INE_M1", category="Equity Scheme - Large Cap Fund", return_1y_pct=10.0, expense_ratio_pct=1.0),
        _fund("INE_M2", category="Equity Scheme - Large Cap Fund", return_1y_pct=20.0, expense_ratio_pct=2.0),
        # segregated — excluded from the mean entirely, even though it carries a value.
        _fund("INE_M3", category="Equity Scheme - Large Cap Fund", return_1y_pct=100.0, is_segregated=True),
    ]
    means = _leaderboard_category_means(funds)
    cat = means["Equity Scheme - Large Cap Fund"]
    assert cat["return_1y_pct"] == 15.0  # (10+20)/2 — 100.0 (segregated) never counted
    assert cat["expense_ratio_pct"] == 1.5
    # No fund in this category supplies sip_xirr_3y_pct -> the key is simply absent.
    assert "sip_xirr_3y_pct" not in cat


def test_perf_rail_attaches_category_avg_matching_computed_means() -> None:
    funds = [
        _fund("INE_P1", category="Equity Scheme - Large Cap Fund", return_3y_pct=20.0),
        _fund("INE_P2", category="Equity Scheme - Large Cap Fund", return_3y_pct=10.0),
    ]
    means = _leaderboard_category_means(funds)
    rows = _build_leaderboard_perf_rail(funds, "return_3y_pct", "pct_3y", means)
    assert rows[0]["metric_category_avg"] == means["Equity Scheme - Large Cap Fund"]["return_3y_pct"]
    assert rows[0]["metric_category_avg"] == 15.0


def test_perf_rail_without_category_means_leaves_avg_none() -> None:
    """A builder call that doesn't pass `category_means` (the pre-V1 call shape)
    keeps working unchanged — metric_category_avg simply stays None."""
    funds = [_fund("INE_P3", return_3y_pct=20.0)]
    rows = _build_leaderboard_perf_rail(funds, "return_3y_pct", "pct_3y")
    assert rows[0]["metric_category_avg"] is None


def test_value_ter_attaches_category_avg() -> None:
    funds = [
        _fund("INE_T1", category="Equity Scheme - Large Cap Fund", expense_ratio_pct=1.0),
        _fund("INE_T2", category="Equity Scheme - Large Cap Fund", expense_ratio_pct=2.0),
    ]
    means = _leaderboard_category_means(funds)
    rows = _build_leaderboard_value_ter(funds, means)
    assert rows[0]["metric_category_avg"] == 1.5


# ---------------------------------------------------------------------------
# 6 — V2 deterministic takeaway sentences (2026-08-16, no LLM)
# ---------------------------------------------------------------------------


def test_takeaway_perf_3y() -> None:
    rows = [
        {"sebi_category": "Equity Scheme - Large Cap Fund", "return_3y_pct": 18.456},
        {"sebi_category": "Equity Scheme - Large Cap Fund", "return_3y_pct": 15.0},
        {"sebi_category": "Debt Scheme - Liquid Fund", "return_3y_pct": 10.0},
    ]
    text = _leaderboard_takeaway("perf_3y", rows)
    assert text == (
        "Most of the strongest 3-year performers right now are Large Cap funds, "
        "with top 3-year total returns around 18.5%."
    )
    _assert_no_advisory_verb(text)


def test_takeaway_sip_3y() -> None:
    rows = [
        {"sebi_category": "Equity Scheme - Mid Cap Fund", "metric_value": 22.3},
        {"sebi_category": "Equity Scheme - Mid Cap Fund", "metric_value": 20.0},
        {"sebi_category": "Hybrid Scheme - Aggressive Hybrid Fund", "metric_value": 15.0},
    ]
    text = _leaderboard_takeaway("sip_3y", rows)
    assert text == "Mid Cap funds lead the 3-year SIP boards, with top XIRRs around 22.3%."
    _assert_no_advisory_verb(text)


def test_takeaway_risk_drawdown() -> None:
    # Rows mirror the now growth-scoped builder (2026-08-16 live review): a
    # cash/liquid fund can no longer reach this board, so the fixture uses the
    # conservative-hybrid funds that legitimately win smallest-drawdown.
    rows = [
        {"sebi_category": "Hybrid Scheme - Conservative Hybrid Fund", "max_drawdown_pct": 0.8},
        {"sebi_category": "Hybrid Scheme - Conservative Hybrid Fund", "max_drawdown_pct": 1.2},
        {"sebi_category": "Equity Scheme - Large Cap Fund", "max_drawdown_pct": 5.0},
    ]
    text = _leaderboard_takeaway("risk_drawdown", rows)
    assert text == "The smallest recent falls among growth funds are around 0.8% — mostly Conservative Hybrid funds."
    _assert_no_advisory_verb(text)


def test_takeaway_value_ter_index_dominant() -> None:
    rows = [
        {"sebi_category": "Other Scheme - Index Funds", "expense_ratio_pct": 0.2},
        {"sebi_category": "Other Scheme - Index Funds", "expense_ratio_pct": 0.3},
        {"sebi_category": "Equity Scheme - Large Cap Fund", "expense_ratio_pct": 1.0},
    ]
    text = _leaderboard_takeaway("value_ter", rows)
    assert text == "The lowest-cost funds charge about 0.20% a year — index funds dominate this board."
    _assert_no_advisory_verb(text)


def test_takeaway_value_ter_non_index_dominant() -> None:
    rows = [
        {"sebi_category": "Equity Scheme - Large Cap Fund", "expense_ratio_pct": 0.5},
        {"sebi_category": "Equity Scheme - Large Cap Fund", "expense_ratio_pct": 0.6},
        {"sebi_category": "Other Scheme - Index Funds", "expense_ratio_pct": 0.2},
    ]
    text = _leaderboard_takeaway("value_ter", rows)
    assert text == "The lowest-cost funds charge about 0.20% a year — mostly Large Cap funds."
    _assert_no_advisory_verb(text)


def test_takeaway_momentum() -> None:
    rows = [
        {"sebi_category": "Equity Scheme - Flexi Cap Fund"},
        {"sebi_category": "Equity Scheme - Flexi Cap Fund"},
        {"sebi_category": "Hybrid Scheme - Aggressive Hybrid Fund"},
    ]
    text = _leaderboard_takeaway("momentum", rows)
    assert text == "Flexi Cap funds are climbing the rankings fastest this period."
    _assert_no_advisory_verb(text)


def test_takeaway_category_inflows() -> None:
    rows = [
        {"category": "Equity Scheme - Large Cap Fund", "net_flow_cr": 12345.678, "period_month": "2026-07"},
    ]
    text = _leaderboard_takeaway("category_inflows", rows)
    assert text == "Investor money moved most into Equity Scheme - Large Cap Fund last month (₹12,345.7 crore net)."
    _assert_no_advisory_verb(text)


def test_takeaway_unsupported_board_key_returns_none() -> None:
    rows = [{"sebi_category": "Equity Scheme - Large Cap Fund", "max_drawdown_pct": 5.0}]
    assert _leaderboard_takeaway("risk_lowest", rows) is None


def test_takeaway_empty_rows_returns_none() -> None:
    assert _leaderboard_takeaway("perf_3y", []) is None
    assert _leaderboard_takeaway("category_inflows", []) is None


# ---------------------------------------------------------------------------
# 7 — serializer: takeaway pass-through (fail-closed on non-str)
# ---------------------------------------------------------------------------


def test_serialize_leaderboard_response_passes_through_str_takeaway() -> None:
    envelope = serialize_leaderboard_response(
        as_of="2026-08-15",
        hero=None,
        boards={"perf_3y": {"title": "t", "rows": [], "takeaway": "Large Cap funds lead."}},
    )
    assert envelope["boards"]["perf_3y"]["takeaway"] == "Large Cap funds lead."


def test_serialize_leaderboard_response_drops_non_str_takeaway() -> None:
    envelope = serialize_leaderboard_response(
        as_of="2026-08-15",
        hero=None,
        boards={"perf_3y": {"title": "t", "rows": [], "takeaway": 42}},
    )
    assert "takeaway" not in envelope["boards"]["perf_3y"]


def test_serialize_leaderboard_response_omits_absent_takeaway() -> None:
    envelope = serialize_leaderboard_response(
        as_of="2026-08-15",
        hero=None,
        boards={"perf_3y": {"title": "t", "rows": []}},
    )
    assert "takeaway" not in envelope["boards"]["perf_3y"]
