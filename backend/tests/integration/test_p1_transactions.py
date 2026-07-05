"""P1 — `holding.transactions` (My Investment / Transactions / Tax seed, FUND_DETAIL_DATA_ARCHITECTURE
_PLAN.md §5 rows 5/17/18, §8, §17).

Pure test proves the payload builder is #2-safe. PG tests prove the NEW
`GET /portfolio/{id}/transactions` route end-to-end through the A3 boundary: owner-scoped reads
(IDOR + in-query owner-scoping, mirroring the holdings/summary pattern), anonymous 401, another
user's portfolio 404, newest-first ordering, the optional `isin` filter, and the server-side cap.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from dhanradar.mf.portfolio_read import transactions_payload
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


def _all_keys(value) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        out |= set(value.keys())
        for v in value.values():
            out |= _all_keys(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            out |= _all_keys(v)
    return out


def _all_values(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _all_values(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _all_values(v)
    else:
        yield value


# --- pure: the payload builder is #2-safe ----------------------------------------------------------


class _Txn:
    """Minimal stand-in for `MfPortfolioTransaction` — only the columns the builder reads."""

    def __init__(self, **kw):
        self.id = kw["id"]
        self.instrument_id = kw["instrument_id"]
        self.folio_number = kw["folio_number"]
        self.txn_type = kw["txn_type"]
        self.txn_date = kw["txn_date"]
        self.units = kw["units"]
        self.nav_or_price = kw.get("nav_or_price")
        self.amount = kw["amount"]


def test_transactions_payload_safe_fields_no_score():
    rows = [
        _Txn(
            id="t1", instrument_id="INF1", folio_number="F1", txn_type="purchase",
            txn_date=date(2026, 1, 15), units=10.0, nav_or_price=100.0, amount=-1000.0,
        ),
    ]
    p = transactions_payload(rows, total=1, portfolio_id="pid-1", isin="INF1", limit=50, offset=0)
    assert "unified_score" not in _all_keys(p) and "score" not in _all_keys(p)
    assert p["portfolio_id"] == "pid-1" and p["isin"] == "INF1"
    assert p["count"] == 1 and p["total"] == 1 and p["limit"] == 50 and p["offset"] == 0
    t = p["transactions"][0]
    assert t["id"] == "t1" and t["isin"] == "INF1" and t["txn_type"] == "purchase"
    assert t["units"] == 10.0 and t["nav_or_price"] == 100.0 and t["amount"] == -1000.0


# --- PG: the new route end-to-end through the boundary, under owner-scoping ------------------------


async def _seed_user(db_session, email: str) -> str:
    u = User(email=email)
    db_session.add(u)
    await db_session.flush()
    uid = str(u.id)
    await db_session.commit()
    return uid


async def _seed_portfolio(db_session, uid: str) -> str:
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'P1') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    await db_session.commit()
    return str(pid)


async def _seed_txn(
    db_session,
    uid: str,
    pid: str,
    isin: str,
    txn_date: date,
    txn_type: str,
    amount: float,
    units: float = 10.0,
    source_ref: str | None = None,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO mf.portfolio_transactions (portfolio_id, user_id, instrument_id,"
            " folio_number, txn_type, txn_date, units, nav_or_price, amount, source, source_ref)"
            " VALUES (:p, :u, :isin, 'F1', :ttype, :d, :units, 100.0, :amt, 'test', :ref)"
        ),
        {
            "p": pid, "u": uid, "isin": isin, "ttype": txn_type, "d": txn_date,
            "units": units, "amt": amount, "ref": source_ref or f"{isin}-{txn_date}-{txn_type}",
        },
    )


async def test_transactions_owner_ok_newest_first(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "p1-owner@test.dev")
    pid = await _seed_portfolio(db_session, uid)
    today = date.today()
    await _seed_txn(db_session, uid, pid, "INF200K01VT2", today - timedelta(days=10), "purchase", -1000.0)
    await _seed_txn(db_session, uid, pid, "INF200K01VT2", today - timedelta(days=5), "sip", -500.0)
    await _seed_txn(db_session, uid, pid, "INF200K02XY3", today - timedelta(days=2), "redemption", 300.0)
    await db_session.commit()
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/transactions", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    env = r.json()
    assert env["status"] == "present" and env["meta"]["content_class"] == "PERSONAL"
    d = env["data"]
    assert d["total"] == 3 and d["count"] == 3
    dates = [t["txn_date"] for t in d["transactions"]]
    assert dates == sorted(dates, reverse=True), "must be newest-first"
    # #2: no raw score anywhere.
    assert "unified_score" not in _all_keys(env)


async def test_transactions_isin_filter(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "p1-filter@test.dev")
    pid = await _seed_portfolio(db_session, uid)
    today = date.today()
    await _seed_txn(db_session, uid, pid, "INF200K01VT2", today - timedelta(days=3), "purchase", -1000.0)
    await _seed_txn(db_session, uid, pid, "INF200K02XY3", today - timedelta(days=1), "purchase", -2000.0)
    await db_session.commit()
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/transactions?isin=INF200K01VT2",
        headers=make_auth_headers(access_token=token),
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["isin"] == "INF200K01VT2"
    assert d["total"] == 1 and len(d["transactions"]) == 1
    assert d["transactions"][0]["isin"] == "INF200K01VT2"


async def test_transactions_cap_enforced(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "p1-cap@test.dev")
    pid = await _seed_portfolio(db_session, uid)
    today = date.today()
    for i in range(5):
        await _seed_txn(
            db_session, uid, pid, "INF200K01VT2", today - timedelta(days=i), "purchase", -100.0
        )
    await db_session.commit()
    token, _ = create_access_token(uid)
    headers = make_auth_headers(access_token=token)

    # server-side limit clamps the page size (5 rows exist, only 2 come back; total still reports 5).
    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/transactions?limit=2", headers=headers
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["count"] == 2 and d["total"] == 5

    # a limit beyond the hard cap (200) is rejected at the boundary (422), never silently served.
    r2 = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/transactions?limit=500", headers=headers
    )
    assert r2.status_code == 422


async def test_transactions_rls_and_auth(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    a = await _seed_user(db_session, "p1-a@test.dev")
    b = await _seed_user(db_session, "p1-b@test.dev")
    pid_a = await _seed_portfolio(db_session, a)
    await _seed_txn(db_session, a, pid_a, "INF200K01VT2", date.today(), "purchase", -1000.0)
    await db_session.commit()
    token_b, _ = create_access_token(b)

    path = f"/api/v1/portfolio/{pid_a}/transactions"
    # B asks for A's portfolio → 404 (IDOR)
    r = await rls_async_client.get(path, headers=make_auth_headers(access_token=token_b))
    assert r.status_code == 404, r.text
    # anonymous → 401
    r2 = await rls_async_client.get(path)
    assert r2.status_code == 401, r2.text
    # a malformed isin query param → 422 (never a 500)
    token_a, _ = create_access_token(a)
    r3 = await rls_async_client.get(
        f"{path}?isin=not-an-isin", headers=make_auth_headers(access_token=token_a)
    )
    assert r3.status_code == 422
