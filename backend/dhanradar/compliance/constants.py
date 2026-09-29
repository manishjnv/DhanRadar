"""
DhanRadar — Shared compliance disclosure constants (B56-f1).

Single source of truth for ``NOT_ADVICE`` / ``DISCLAIMER_VERSION`` /
``DISCLOSURE_BUNDLE`` (non-neg #9, architecture §9). Previously defined inside
``scoring/engine/schemas.py``; moved here so non-scoring consumers (dashboard,
mood, education, concepts, notifications, ...) import from a compliance-owned
module instead of reaching into the scoring engine's internal schema module.
``scoring/engine/schemas.py`` re-exports these three names unchanged so no
scoring logic changes.

Values are byte-identical to the pre-move constants — this is a pure move,
zero behaviour change.
"""

from __future__ import annotations

NOT_ADVICE = "NOT_ADVICE"
DISCLAIMER_VERSION = "2026-06-06.v1"
DISCLOSURE_BUNDLE = (
    "Educational analysis only — not investment advice. Labels describe "
    "category-relative form, not a recommendation to buy, sell, hold, or switch."
)
