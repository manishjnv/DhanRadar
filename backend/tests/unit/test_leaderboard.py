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
"""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace
from typing import Any

from fastapi import Response

from dhanradar.mf.serialization import FORBIDDEN_SCORE_KEYS, serialize_leaderboard_response
from dhanradar.tasks.mf import (
    _build_leaderboard_champions,
    _build_leaderboard_hero,
    _build_leaderboard_label_upgrades,
    _build_leaderboard_movers,
    _build_leaderboard_top100,
    _dedupe_leaderboard_variants,
    _leaderboard_is_stale,
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


def _fund(isin: str, *, category: str = "Large Cap Fund", rank: int = 1, total: int = 10, **extra: Any) -> dict:
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
        _fund("INE000A01011", fund_name_short="Alpha Fund", category="Large Cap Fund", rank=1, total=10),
        # Same scheme, worse-ranked plan variant — must be dropped, never shown twice.
        _fund("INE000A01022", fund_name_short="Alpha Fund", category="Large Cap Fund", rank=4, total=10),
        # Better within-category percentile (1/50=0.02) than Alpha's 1/10=0.1.
        _fund("INE000B02011", fund_name_short="Beta Fund", category="Mid Cap Fund", rank=1, total=50),
    ]
    rows = _build_leaderboard_top100(funds)
    isins = [r["isin"] for r in rows]

    assert "INE000A01022" not in isins, "duplicate scheme plan/option variant must not appear"
    assert isins == ["INE000B02011", "INE000A01011"]
    # FundRow shape only — never a score field.
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
