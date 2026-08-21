"""Route-registration guard for the MF router.

Regression test for PR #633, where inserting the /watchlist/alerts endpoint
silently consumed the @router.get("/watchlist/summary") decorator — every
existing test called the handler as a plain function, so a de-registered
route sailed through CI while prod would 404.
"""

from __future__ import annotations

from dhanradar.mf.router import router

_REQUIRED_PATHS = {
    "/mf/watchlist/alerts",
    "/mf/watchlist/summary",
    "/mf/watchlist/cards",
    "/mf/compare/bundle",
    "/mf/search",
}


def test_critical_mf_routes_are_registered() -> None:
    paths = {route.path for route in router.routes}
    missing = _REQUIRED_PATHS - paths
    assert not missing, f"MF routes lost their decorator: {sorted(missing)}"
