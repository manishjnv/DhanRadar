"""Route-registration guard for the insights portfolio router.

Regression test for router decorator loss (RCA 2026-08-21): if a route decorator
is accidentally removed while inserting a nearby endpoint, the path silently
disappears even when direct handler-call tests still pass.
"""

from __future__ import annotations

from dhanradar.insights.router import router

_REQUIRED_PATHS = {
    "/portfolio/{portfolio_id}/overlap",
    "/portfolio/{portfolio_id}/holdings",
    "/portfolio/{portfolio_id}/transactions",
    "/portfolio/{portfolio_id}/fit",
    "/portfolio/{portfolio_id}/summary",
    "/portfolio/{portfolio_id}/risk",
    "/portfolio/{portfolio_id}/allocation",
    "/portfolio/{portfolio_id}/concentration",
    "/portfolio/{portfolio_id}/diversification",
    "/portfolio/{portfolio_id}/valuation-series",
    "/portfolio/{portfolio_id}/mood-context",
    "/portfolio/{portfolio_id}/performance",
    "/portfolio/{portfolio_id}/cost",
    "/portfolio/{portfolio_id}/health",
}


def test_critical_insights_routes_are_registered() -> None:
    paths = {route.path for route in router.routes}
    missing = _REQUIRED_PATHS - paths
    assert not missing, f"Insights routes lost their decorator: {sorted(missing)}"
