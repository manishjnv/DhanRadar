"""
DhanRadar — Dashboard module (B56).

Read-only aggregation for the post-login home screen. Three endpoints:

  * GET /api/v1/portfolio/summary        — the user's own MF portfolio rollup.
  * GET /api/v1/indices                  — market index levels (Yahoo, cached).
  * GET /api/v1/instruments/top-scored   — the user's own funds ranked by label.

Module isolation (non-neg #7): reads ONLY the `mf` schema (published holdings +
score-result tables) and the shared Yahoo provider / Redis. It never imports or
calls the scoring engine, billing, or any other module's internals — scoring
output is consumed as already-persisted label+band, never recomputed. The public
payload is label + confidence band only; `unified_score` is never serialized
(non-neg #2).
"""
