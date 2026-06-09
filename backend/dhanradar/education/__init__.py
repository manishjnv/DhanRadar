"""
DhanRadar — Tax-Education module (G8).

A financial-year-aware EDUCATIONAL content engine on Indian mutual-fund taxation.
Pure education, never advice — describes tax rules, never recommends an action.
Static / calendar-driven: NO AI generation, NO live market data, NO scoring.

Public-read (anonymous-accessible + crawlable — SEO is the point). Three endpoints
under `/api/v1/learn/tax` serve seeded content (`content.py` → `education`
schema via `seed.py`) + an FY-aware key-date calendar computed at request time.

Every response carries the not-advice disclosure bundle (non-neg #9). All figures
are dated to the financial year they apply to and are general, never personalised.
"""
