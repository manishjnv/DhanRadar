"""M2.3 — TRUE portfolio Sharpe/Sortino/volatility/max-drawdown/recovery (resolves B88's deferral).

Covers:
  * PG: GET /portfolio/{id}/risk — a dense daily-valuation series (>= 90 rows) flips
    `risk_band_basis` to "portfolio return series" and populates max_drawdown_pct (a real number,
    not the B88 None). A short series (< 90 rows, or none at all) keeps the ORIGINAL fallback
    unchanged — `risk_band_basis` = "average fund volatility", ratios/drawdown/recovery None.
  * PG: the exact _MIN_TRUE_RISK_ROWS = 90 boundary (89 rows falls back, 90 rows goes true).
  * PG: `?advanced=true` plus-gating is UNCHANGED by this feature — still 402 for a free user,
    even with a dense true-mode series behind it.
  * Pure: risk_advanced_payload serves real sharpe/sortino/rolling_1y_pct_positive when the
    PortfolioRisk was built from the true series (basis-driven, not touching serialization/gating).

Mirrors test_m2_3_xirr_window.py (the proven M2.3 pattern). Each test seeds a UNIQUE ISIN —
mf_nav_history/mf_funds are shared across the session-scoped DB.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from dhanradar.mf.portfolio_read import (
    _MIN_TRUE_RISK_ROWS,
    PortfolioRisk,
    risk_advanced_payload,
)
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# PG fixtures (self-contained — duplicated from the M2.2/M2.3 proven pattern)
# ---------------------------------------------------------------------------


async def _seed_user(db_session, email: str) -> str:
    u = User(email=email)
    db_session.add(u)
    await db_session.flush()
    uid = str(u.id)
    await db_session.commit()
    return uid


async def _seed_portfolio(db_session, uid: str, isin: str, vol: float = 12.0) -> str:
    """A portfolio with one holding + a fund_metrics row (so the fallback path has a real
    volatility_pct to report). Each test MUST pass a UNIQUE isin — mf_nav_history/mf_funds are
    shared across the session-scoped DB (ON CONFLICT DO NOTHING), so a reused ISIN leaks state
    across tests (the CI-only failure this file's caller was warned about)."""
    pid = (
        await db_session.execute(
            text(
                "INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'TrueRisk') RETURNING id"
            ),
            {"u": uid},
        )
    ).scalar_one()
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_funds (isin, scheme_name, category, sebi_category, is_segregated)"
            " VALUES (:i, 'Test Fund', 'Equity', 'Flexi Cap Fund', false)"
            " ON CONFLICT (isin) DO NOTHING"
        ),
        {"i": isin},
    )
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_nav_history (isin, nav_date, nav) VALUES (:i, :d, 100.0)"
            " ON CONFLICT (isin, nav_date) DO NOTHING"
        ),
        {"i": isin, "d": date.today()},
    )
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_fund_metrics (isin, volatility_pct, max_drawdown_pct, sharpe_ratio,"
            " sortino_ratio, rolling_1y_avg_pct, rolling_1y_pct_positive, as_of_date)"
            " VALUES (:i, :v, -20.0, 1.1, 1.4, 11.0, 60.0, :d) ON CONFLICT (isin) DO NOTHING"
        ),
        {"i": isin, "v": vol, "d": date.today()},
    )
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_user_holdings (user_id, portfolio_id, isin, folio_number, units,"
            " invested_amount, avg_cost_nav, source, as_of_date)"
            " VALUES (:u, :p, :i, '999', 100.0, 9000.0, 90.0, 'cas', :d)"
        ),
        {"u": uid, "p": str(pid), "i": isin, "d": date.today()},
    )
    await db_session.commit()
    return str(pid)


async def _seed_daily_series(db_session, pid: str, uid: str, n_rows: int) -> None:
    """Insert `n_rows` consecutive daily valuation rows ending TODAY, with a zig-zag value pattern
    (guarantees a real drawdown + non-zero volatility) and CONSTANT total_invested (no capital
    flow, so flow-adjusted return == raw pct change — isolates the wealth-index/drawdown math from
    the flow-adjustment math, which has its own dedicated unit tests)."""
    today = date.today()
    start = today - timedelta(days=n_rows - 1)
    rows = []
    value = 100_000.0
    for i in range(n_rows):
        # Zig-zag: mostly drifts up, with periodic dips deep enough to register as drawdowns.
        if i % 7 == 0 and i > 0:
            value *= 0.90  # a ~10% dip every 7th day
        else:
            value *= 1.01
        rows.append(
            {
                "p": pid,
                "u": uid,
                "d": start + timedelta(days=i),
                "v": round(value, 2),
                "i": 90_000.0,
            }
        )
    for r in rows:
        await db_session.execute(
            text(
                "INSERT INTO mf.mf_portfolio_daily_values"
                " (portfolio_id, user_id, valuation_date, total_value, total_invested)"
                " VALUES (:p, :u, :d, :v, :i) ON CONFLICT (portfolio_id, valuation_date) DO NOTHING"
            ),
            r,
        )
    await db_session.commit()


# ---------------------------------------------------------------------------
# PG: GET /risk — true series vs fallback, and the exact row-count boundary
# ---------------------------------------------------------------------------


async def test_dense_series_flips_to_true_basis_with_real_drawdown(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "tr-dense@test.dev")
    pid = await _seed_portfolio(db_session, uid, isin="INFTRD001")
    await _seed_daily_series(db_session, pid, uid, n_rows=120)
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/risk", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["risk_band_basis"] == "portfolio return series"
    assert d["volatility_pct"] is not None and d["volatility_pct"] > 0
    assert d["max_drawdown_pct"] is not None and d["max_drawdown_pct"] > 0
    assert d["risk_band"] in {"low", "moderate", "high", "very_high"}


async def test_short_series_keeps_the_original_fallback(db_session, rls_async_client):
    """Only 10 daily-value rows (< _MIN_TRUE_RISK_ROWS) → the ORIGINAL value-weighted fallback,
    unchanged: basis = average fund volatility, drawdown/recovery/sharpe/sortino stay None."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "tr-short@test.dev")
    pid = await _seed_portfolio(db_session, uid, isin="INFTRD002", vol=15.0)
    await _seed_daily_series(db_session, pid, uid, n_rows=10)
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/risk", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["risk_band_basis"] == "average fund volatility"
    assert d["volatility_pct"] == pytest.approx(
        15.0
    )  # the single fund's own metric, value-weighted
    assert d["max_drawdown_pct"] is None
    assert d["recovery_months"] is None


async def test_no_daily_values_at_all_keeps_the_original_fallback(db_session, rls_async_client):
    """Cold start — zero mf_portfolio_daily_values rows → same honest fallback (no crash)."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "tr-cold@test.dev")
    pid = await _seed_portfolio(db_session, uid, isin="INFTRD003")
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/risk", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["risk_band_basis"] == "average fund volatility"
    assert d["max_drawdown_pct"] is None


async def test_exact_min_true_risk_rows_boundary(db_session, rls_async_client):
    """89 rows falls back; 90 rows (the exact _MIN_TRUE_RISK_ROWS) goes true — pins the boundary."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    assert _MIN_TRUE_RISK_ROWS == 90

    uid_a = await _seed_user(db_session, "tr-boundary-below@test.dev")
    pid_a = await _seed_portfolio(db_session, uid_a, isin="INFTRD004")
    await _seed_daily_series(db_session, pid_a, uid_a, n_rows=_MIN_TRUE_RISK_ROWS - 1)
    token_a, _ = create_access_token(uid_a)
    r_a = await rls_async_client.get(
        f"/api/v1/portfolio/{pid_a}/risk", headers=make_auth_headers(access_token=token_a)
    )
    assert r_a.json()["data"]["risk_band_basis"] == "average fund volatility"

    uid_b = await _seed_user(db_session, "tr-boundary-at@test.dev")
    pid_b = await _seed_portfolio(db_session, uid_b, isin="INFTRD005")
    await _seed_daily_series(db_session, pid_b, uid_b, n_rows=_MIN_TRUE_RISK_ROWS)
    token_b, _ = create_access_token(uid_b)
    r_b = await rls_async_client.get(
        f"/api/v1/portfolio/{pid_b}/risk", headers=make_auth_headers(access_token=token_b)
    )
    assert r_b.json()["data"]["risk_band_basis"] == "portfolio return series"


# ---------------------------------------------------------------------------
# PG: ?advanced=true tier-gating is UNCHANGED by this feature
# ---------------------------------------------------------------------------


async def test_advanced_still_402_for_free_user_even_with_dense_true_series(
    db_session, rls_async_client
):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "tr-adv-402@test.dev")
    pid = await _seed_portfolio(db_session, uid, isin="INFTRD006")
    await _seed_daily_series(db_session, pid, uid, n_rows=120)
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/risk?advanced=true", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 402, f"{r.status_code}: {r.text}"  # tier-gate unchanged by M2.3


# ---------------------------------------------------------------------------
# Pure: risk_advanced_payload serves the true ratios once the basis says so
# ---------------------------------------------------------------------------


def test_advanced_payload_serves_true_sharpe_sortino_rolling_positive():
    r = PortfolioRisk(
        volatility_pct=16.2,
        max_drawdown_pct=22.5,
        sharpe_ratio=0.85,
        sortino_ratio=1.10,
        rolling_1y_avg_pct=13.4,
        rolling_1y_pct_positive=72.0,
        fund_count=4,
        funds_with_metrics=4,
        as_of="2026-07-03",
        recovery_months=5,
        risk_band_basis="portfolio return series",
    )
    p = risk_advanced_payload(r, "pid-true")
    assert p["sharpe_ratio"] == 0.85
    assert p["sortino_ratio"] == 1.10
    assert p["rolling_1y_pct_positive"] == 72.0
    assert p["alpha"] is None and p["beta"] is None  # still out of scope (ADR-0033b)
