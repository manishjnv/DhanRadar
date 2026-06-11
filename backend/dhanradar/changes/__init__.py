"""
DhanRadar — What Changed explainability module (Plan Group 2).

Read-only. Consumes mf.* history tables via get_snapshot_history() and
derives per-fund label/band diff information for educational display.

No numeric score, no unified_score, no raw confidence float anywhere in
this module. Labels and confidence bands only (non-neg #2).
SEBI educational boundary: all copy is descriptive (category-relative form),
never advisory (non-neg #1).
"""
