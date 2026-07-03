"""PR-C — hero money view + Section-2 TWR return line: DB-integration contract tests.

Covers (pure-math cases for twr_index_series itself live in test_mf_valuation.py):
  * PG: GET /valuation-series -> first_investment_date from the ledger (portfolio_transactions).
  * PG: GET /valuation-series -> first_investment_date falls back to the first series row when
    the ledger has no rows yet (a pre-ledger portfolio).
  * PG: GET /valuation-series -> first_investment_date is None on a genuine cold start (no ledger,
    no series).
  * PG: GET /valuation-series -> each point carries twr_index; a same-day deposit leaves it flat
    (the founder-reported +212% fake-gain bug this PR fixes).

Self-contained seed helpers (own isin/portfolio per test) per the C-wave convention recorded in
test_m2_2_portfolio_value_series.py: the DB is session-scoped and shared across tests, so a reused
isin/portfolio silently carries state from one test into another.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


async def _seed_user(db_session, email: str) -> str:
    u = User(email=email)
    db_session.add(u)
    await db_session.flush()
    uid = str(u.id)
    await db_session.commit()
    return uid


async def _seed_portfolio(db_session, uid: str, name: str) -> str:
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, :n) RETURNING id"),
            {"u": uid, "n": name},
        )
    ).scalar_one()
    await db_session.commit()
    return str(pid)


async def _seed_daily_values(
    db_session, pid: str, uid: str, rows: list[tuple[date, float, float]]
) -> None:
    for vdate, total_value, total_invested in rows:
        await db_session.execute(
            text(
                "INSERT INTO mf.mf_portfolio_daily_values"
                " (portfolio_id, user_id, valuation_date, total_value, total_invested)"
                " VALUES (:p, :u, :d, :v, :i)"
                " ON CONFLICT (portfolio_id, valuation_date) DO NOTHING"
            ),
            {"p": pid, "u": uid, "d": vdate, "v": total_value, "i": total_invested},
        )
    await db_session.commit()


async def _seed_txn(
    db_session, pid: str, uid: str, isin: str, txn_date: date, units: float, amount: float, source_ref: str
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO mf.portfolio_transactions"
            " (portfolio_id, user_id, asset_class, instrument_id, folio_number, txn_type,"
            "  txn_date, units, nav_or_price, amount, source, source_ref, parser_version)"
            " VALUES (:p, :u, 'mf', :i, '999', 'purchase', :d, :un, 100.0, :a, 'cas', :sr, 'cas-1')"
        ),
        {"p": pid, "u": uid, "i": isin, "d": txn_date, "un": units, "a": amount, "sr": source_ref},
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# PG: GET /valuation-series -> first_investment_date
# ---------------------------------------------------------------------------


async def test_first_investment_date_from_ledger(db_session, rls_async_client):
    """The ledger's EARLIEST txn_date wins, even when it predates the daily-value series."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "prc-ledger@test.dev")
    pid = await _seed_portfolio(db_session, uid, "PRC-Ledger")
    await _seed_txn(db_session, pid, uid, "INFPRC0001", date(2025, 3, 15), 10.0, -1000.0, "prc-ledger-1")
    await _seed_daily_values(
        db_session, pid, uid, [(date(2026, 6, 1), 1000.0, 1000.0), (date(2026, 6, 2), 1010.0, 1000.0)]
    )
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/valuation-series", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["first_investment_date"] == "2025-03-15"


async def test_first_investment_date_falls_back_to_series_start(db_session, rls_async_client):
    """No ledger rows (a pre-ledger portfolio) -> falls back to the first daily-value row's date."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "prc-noledger@test.dev")
    pid = await _seed_portfolio(db_session, uid, "PRC-NoLedger")
    await _seed_daily_values(
        db_session, pid, uid, [(date(2026, 5, 1), 1000.0, 1000.0), (date(2026, 5, 2), 1010.0, 1000.0)]
    )
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/valuation-series", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["first_investment_date"] == "2026-05-01"


async def test_first_investment_date_none_on_cold_start(db_session, rls_async_client):
    """No ledger, no daily-value rows -> None (honest, not fabricated); points is empty too."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "prc-cold@test.dev")
    pid = await _seed_portfolio(db_session, uid, "PRC-Cold")
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/valuation-series", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["first_investment_date"] is None
    assert d["points"] == []


# ---------------------------------------------------------------------------
# PG: GET /valuation-series -> twr_index per point
# ---------------------------------------------------------------------------


async def test_twr_index_present_and_deposit_neutral(db_session, rls_async_client):
    """A same-day 500 deposit (V and I both jump 500, no price move) leaves twr_index flat — the
    founder-reported +212% fake-gain bug (a large deposit rebased on window-start VALUE) this PR
    fixes."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "prc-twr@test.dev")
    pid = await _seed_portfolio(db_session, uid, "PRC-Twr")
    await _seed_daily_values(
        db_session,
        pid,
        uid,
        [(date(2026, 6, 1), 1000.0, 1000.0), (date(2026, 6, 2), 1500.0, 1500.0)],  # deposit day
    )
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/valuation-series", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    pts = r.json()["data"]["points"]
    assert pts[0]["twr_index"] == pytest.approx(100.0)
    assert pts[1]["twr_index"] == pytest.approx(100.0)  # flat -- a deposit is not a return


async def test_twr_index_reflects_a_real_market_move(db_session, rls_async_client):
    """A pure 5% value gain (invested unchanged) DOES move twr_index — it only neutralises flows,
    not genuine market moves."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "prc-twrmove@test.dev")
    pid = await _seed_portfolio(db_session, uid, "PRC-TwrMove")
    await _seed_daily_values(
        db_session,
        pid,
        uid,
        [(date(2026, 6, 1), 1000.0, 1000.0), (date(2026, 6, 2), 1050.0, 1000.0)],  # +5%, no flow
    )
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/valuation-series", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    pts = r.json()["data"]["points"]
    assert pts[0]["twr_index"] == pytest.approx(100.0)
    assert pts[1]["twr_index"] == pytest.approx(105.0)
