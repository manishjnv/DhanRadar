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

Block 0.5 findings (2026-07-06, real-browser-UA curl probes; no bypass attempted):
  - HDFC:  still bot-blocked. Every page (including the homepage) returns HTTP 403
    with an Akamai "Access Denied" edgesuite.net error page.
  - KOTAK: still bot-blocked. The homepage 302-redirects to
    validate.perfdrive.com (Radware Bot Manager's challenge domain;
    `ssk=botmanager_support@radware.com` in the query string).
  - ICICI_PRU: NOT a classic WAF/CAPTCHA block (no Akamai/Radware evidence) — but
    every content sub-route (e.g. /about-us, /portfolio-disclosure) 404s on a plain
    HTTP GET; only "/" and "/sitemap.xml" resolve. This is a client-side-only SPA
    with no discoverable JSON API in the initial HTML — functionally unreachable
    for the httpx-only fetchers here without a JS-executing browser (out of scope
    for this pass). Left in BOT_BLOCKED_AMCS (no working fetcher).
  - AXIS: same story as ICICI_PRU — homepage and disclosure pages return HTTP 200
    (not blocked), and the site is Drupal-backed (static files served from
    /cms/sites/default/files/...), but the actual TER/portfolio data is loaded via
    a client-side API call whose endpoint is not discoverable from the
    server-rendered HTML alone. Left in BOT_BLOCKED_AMCS (no working fetcher).
  - SBI:  REMOVED from BOT_BLOCKED_AMCS. SBI's factsheet/portfolio JS widgets are
    also JS-rendered, but its "/total-expense-ratio" page is a plain
    server-rendered HTML page linking directly to a static xlsx
    (docs/default-source/ter_allschemes/current-year-ter.xlsx) — verified
    reachable, real data, no bot-block anywhere on the domain. See
    `dhanradar.market_data.amc_expense_sbi` (dedicated fetcher, wired directly
    into tasks/mf_expense_ratio.py — same pattern as UTI/NIPPON for fund managers).
"""

from __future__ import annotations

# AMCs with known bot protection — factsheet scraping is not automatable (Admin.md §12 Q3).
# SBI removed 2026-07-06 (Block 0.5): not bot-blocked; has a dedicated TER fetcher
# (amc_expense_sbi.fetch_sbi_expense_ratios) wired directly into
# tasks/mf_expense_ratio.py, bypassing this list entirely (same pattern as UTI/NIPPON
# for fund managers — see the module docstring above for the full evidence).
BOT_BLOCKED_AMCS: frozenset[str] = frozenset({"HDFC", "ICICI_PRU", "KOTAK", "AXIS"})

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
