"""
DhanRadar — shared AMC registry for factsheet-derived sources (Phase 6).

The expense-ratio and fund-manager tasks both scrape AMC factsheet / disclosure
pages. This module is the single source of the AMC list + the set of AMCs whose
sites are bot-protected (Akamai / Radware) and therefore have NO reliable automated
fetch. Per Admin.md §12 Q3, there is no automated workaround for these — tasks must
degrade gracefully (mark the source unreachable, record the blocked AMCs in the run
metadata) and NEVER crash or retry-spin.

Kept deliberately small and read-only; the broker/Playwright disclosure roots in
tasks/mf.py (_AMC_DISCLOSURE_ROOTS) are a separate concern (monthly constituents).
"""

from __future__ import annotations

# AMCs with known bot protection — factsheet scraping is not automatable (Admin.md §12 Q3).
BOT_BLOCKED_AMCS: frozenset[str] = frozenset(
    {"HDFC", "SBI", "ICICI_PRU", "KOTAK", "AXIS"}
)

# Best-effort factsheet landing pages for AMCs that DO serve parseable pages.
# (Bot-blocked AMCs above are intentionally excluded — including them just guarantees
# a failed fetch every run.) Extend as more AMCs are verified scrapeable.
#
# UTI and NIPPON are intentionally NOT listed here (Phase 6 rebuild, 2026-07):
# neither serves delimited rows this generic factsheet-HTML parser understands.
# UTI has a dedicated JSON-API fetcher (amc_managers_uti.fetch_uti_fund_managers)
# and NIPPON has a dedicated factsheet-PDF fetcher
# (amc_managers_nippon.fetch_nippon_fund_managers) — both wired directly into
# tasks/mf_fund_manager.py alongside this generic list, so they are not
# double-counted (once as format_mismatch here, once as ok there).
AMC_FACTSHEET_SOURCES: list[dict[str, str]] = [
    {"name": "MIRAE", "url": "https://www.miraeassetmf.co.in/downloads/factsheet"},
    {"name": "DSP", "url": "https://www.dspim.com/downloads"},
    {"name": "FRANKLIN", "url": "https://www.franklintempletonindia.com/investor/factsheet"},
]


def is_bot_blocked(amc_name: str) -> bool:
    """True if this AMC's site is bot-protected (no automated factsheet fetch)."""
    return amc_name.upper() in BOT_BLOCKED_AMCS
