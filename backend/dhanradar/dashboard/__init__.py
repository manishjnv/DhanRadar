"""
DhanRadar — Dashboard module (B56).

The old post-login home screen (/dashboard) was decommissioned and folded into
/mf/portfolio. What remains here is public market-data reads, unrelated to any
per-user aggregation:

  * GET /api/v1/indices — market index levels (Yahoo, cached).
  * dashboard/ticker.py — the global ticker-bar quotes (mounted via mood/router.py).

Module isolation (non-neg #7): reads only the shared Yahoo provider / Redis. It
never imports or calls the scoring engine, billing, or any other module's
internals.
"""
