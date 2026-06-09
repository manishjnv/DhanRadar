"""
DhanRadar — Tax-Education seed content (G8).

The authored source of truth for the `education.tax_education_articles` table.
Lives under `backend/dhanradar/` so the `ci_guards` advisory-verb scan covers it.
Loaded by the idempotent `dhanradar.education.seed` command.

EDUCATION ONLY — every article describes a tax rule; none recommends an action.
All figures are for **FY 2025-26 (AY 2026-27)** under the Income-tax Act as amended
by the Finance Act 2024 (changes effective for transfers on or after 23 July 2024),
and each is shown with its FY label + a dated source note. Tax rules change yearly;
this content must be reviewed against the prevailing Finance Act before each FY.
"""

from __future__ import annotations

# Education-specific not-advice disclosure (non-neg #9). NOT_ADVICE +
# DISCLAIMER_VERSION are imported read-only from the shared compliance constants in
# service.py — this string is the education surface's own contextual disclosure.
EDUCATION_DISCLOSURE = (
    "General educational information on Indian mutual-fund taxation — not tax or "
    "investment advice. Tax rules and figures change and depend on your individual "
    "circumstances; consult a qualified professional before acting on any of this."
)

# Human-readable not-advice line shown on every education surface. The education
# module supplies its OWN text rather than the platform `NOT_ADVICE` marker token
# (which is a literal flag, not display copy) so the public pages render a real
# sentence, never the bare word "NOT_ADVICE".
EDUCATION_NOT_ADVICE = "Not tax or investment advice."

_FY = "FY 2025-26 (AY 2026-27)"
_SRC = (
    "Based on the Income-tax Act as amended by the Finance Act 2024 (capital-gains "
    "changes effective for transfers on or after 23 July 2024) and the Finance Act 2025; "
    "applicable FY 2025-26."
)


# Each dict maps 1:1 to education.TaxEducationArticle columns (minus updated_at).
ARTICLES: list[dict] = [
    {
        "slug": "capital-gains-basics",
        "title": "How mutual-fund gains are taxed: the basics",
        "summary": "The two things that decide mutual-fund tax — the type of fund and how long the units were held.",
        "category": "Capital gains",
        "fy_label": _FY,
        "sort_order": 10,
        "source_note": _SRC,
        "body_md": (
            "## Two questions decide the tax\n\n"
            "For any mutual-fund redemption, the tax treatment follows from two facts:\n\n"
            "1. **What type of fund is it?** Tax law splits funds into **equity-oriented** "
            "(at least 65% in domestic equity) and **other / specified funds** (such as most "
            "debt funds).\n"
            "2. **How long were the units held?** This sets whether a gain is **short-term** "
            "or **long-term**, and the holding-period threshold differs by fund type.\n\n"
            "## Equity-oriented funds (FY 2025-26)\n\n"
            "- Held 12 months or less: short-term, taxed at **20%**.\n"
            "- Held more than 12 months: long-term, taxed at **12.5%** on gains above "
            "**₹1.25 lakh** in the financial year.\n\n"
            "## Specified / debt funds\n\n"
            "For units acquired on or after **1 April 2023**, the whole gain is taxed at the "
            "investor's **income-tax slab rate**, regardless of holding period.\n\n"
            "## Hybrid funds\n\n"
            "A hybrid scheme is taxed by its equity content: **65% or more** in domestic equity "
            "is taxed like an equity fund; a debt-oriented hybrid (over **65%** in debt/money-"
            "market) is taxed at slab rates as a specified fund; a fund in between follows the "
            "residual capital-gains rules.\n\n"
            "This overview is general and applies to FY 2025-26; see the linked topics for detail."
        ),
    },
    {
        "slug": "equity-fund-taxation",
        "title": "How equity mutual funds are taxed",
        "summary": "Holding periods, short-term vs long-term gains, and the ₹1.25 lakh LTCG exemption for equity-oriented funds.",
        "category": "Capital gains",
        "fy_label": _FY,
        "sort_order": 20,
        "source_note": _SRC,
        "body_md": (
            "## What counts as an equity fund\n\n"
            "A scheme is **equity-oriented** for tax purposes when it invests at least **65%** "
            "of its assets in domestic equity shares.\n\n"
            "## Holding period\n\n"
            "- **Short-term:** units held for **12 months or less**.\n"
            "- **Long-term:** units held for **more than 12 months**.\n\n"
            "## Rates (FY 2025-26)\n\n"
            "- **Short-term capital gains (STCG)** on equity-oriented funds are taxed at "
            "**20%** under Section 111A.\n"
            "- **Long-term capital gains (LTCG)** are taxed at **12.5%** under Section 112A, on "
            "gains **above ₹1.25 lakh** in a financial year. The first ₹1.25 lakh of long-term "
            "gains in the year is exempt, and indexation does not apply.\n\n"
            "## Worked illustration\n\n"
            "If long-term gains in the year total ₹1.75 lakh, the first ₹1.25 lakh is exempt and "
            "the remaining ₹50,000 is taxed at 12.5% (₹6,250), plus any applicable surcharge and "
            "cess. This illustration is general; actual tax depends on the full return.\n\n"
            "These figures apply to FY 2025-26 and change from year to year."
        ),
    },
    {
        "slug": "debt-fund-taxation",
        "title": "How debt mutual funds are taxed",
        "summary": "Why most debt-fund gains are taxed at the slab rate, and how the April 2023 cut-off changed the rules.",
        "category": "Capital gains",
        "fy_label": _FY,
        "sort_order": 30,
        "source_note": _SRC,
        "body_md": (
            "## The April 2023 cut-off\n\n"
            "For units of a **specified mutual fund** — for FY 2025-26 (AY 2026-27), a fund that "
            "invests **more than 65% of its assets in debt and money-market instruments** — that "
            "were **acquired on or after 1 April 2023**, the entire capital gain is treated as "
            "**short-term** and taxed at the investor's **income-tax slab rate**, regardless of "
            "how long the units are held (Section 50AA). There is no separate long-term rate and "
            "no indexation for these units.\n\n"
            "The Finance Act 2024 narrowed this definition (from AY 2026-27): it now targets "
            "debt-oriented funds (over 65% in debt/money-market). Some funds caught by the older "
            "'not more than 35% equity' test — such as certain ETFs, gold funds, and 35–65% "
            "hybrids — are no longer specified funds and follow the residual capital-gains "
            "rules instead.\n\n"
            "## Units acquired before 1 April 2023\n\n"
            "Older units follow the earlier rules. After the Finance Act 2024, long-term gains "
            "(units held more than 36 months) on transfers made on or after 23 July 2024 are "
            "taxed at **12.5% without indexation**; short-term gains are taxed at the slab rate.\n\n"
            "## Why the purchase date matters\n\n"
            "Because the acquisition date decides the rule, the date and cost of each lot of "
            "units matter. The fund house's capital-gains statement separates lots by purchase "
            "date.\n\n"
            "Figures are general and apply to FY 2025-26; these rules change from year to year."
        ),
    },
    {
        "slug": "elss-and-section-80c",
        "title": "ELSS funds, the 3-year lock-in, and Section 80C",
        "summary": "What the ELSS lock-in means, how the Section 80C deduction works, and why the chosen tax regime matters.",
        "category": "Deductions",
        "fy_label": _FY,
        "sort_order": 40,
        "source_note": _SRC,
        "body_md": (
            "## The 3-year lock-in\n\n"
            "An **Equity Linked Savings Scheme (ELSS)** is an equity-oriented fund with a "
            "statutory **3-year lock-in**. Each investment — including each SIP instalment — is "
            "locked for three years from its own date, so units cannot be redeemed before then.\n\n"
            "## Section 80C\n\n"
            "Investment in ELSS qualifies for a deduction under **Section 80C**, within the "
            "overall 80C ceiling of **₹1.5 lakh** per financial year. This deduction is available "
            "**only under the old tax regime**. The new tax regime — the default from FY 2023-24 "
            "— does not allow the Section 80C deduction.\n\n"
            "## Taxation on redemption\n\n"
            "After the lock-in, gains are taxed under the **equity-fund rules**: long-term gains "
            "above ₹1.25 lakh in the year at 12.5%, and short-term gains at the equity rate of "
            "20% (Section 111A), for FY 2025-26.\n\n"
            "This is general information for FY 2025-26 and is not a recommendation; the "
            "deduction, ceiling, and regime rules change from year to year."
        ),
    },
    {
        "slug": "idcw-dividend-taxation",
        "title": "How IDCW (dividend) payouts are taxed",
        "summary": "IDCW is added to total income and taxed at the slab rate, with TDS once it crosses ₹10,000 in a year.",
        "category": "Income",
        "fy_label": _FY,
        "sort_order": 50,
        "source_note": _SRC,
        "body_md": (
            "## IDCW is taxed as income\n\n"
            "The **IDCW** option (Income Distribution cum Capital Withdrawal, formerly labelled "
            "the dividend option) distributes part of a fund's value. Since FY 2020-21, an IDCW "
            "payout is **added to the investor's total income** and taxed at the applicable "
            "**slab rate** — there is no separate concessional rate.\n\n"
            "## TDS under Section 194K\n\n"
            "The fund house deducts **TDS at 10%** on IDCW paid to a resident investor when the "
            "total IDCW from that fund exceeds **₹10,000** in a financial year (the threshold was "
            "raised from ₹5,000 with effect from 1 April 2025). The TDS is adjusted against the "
            "final tax liability when the return is filed.\n\n"
            "## Growth vs IDCW\n\n"
            "Under the **Growth** option no payout is made, so there is no annual IDCW to tax; "
            "gains are then taxed only on redemption under the capital-gains rules. The "
            "difference between Growth and IDCW is about **when** income is taxed — a factual "
            "distinction, not a recommendation.\n\n"
            "Figures are general and apply to FY 2025-26."
        ),
    },
    {
        "slug": "exit-loads-explained",
        "title": "Exit loads: what they are (and what they are not)",
        "summary": "An exit load is a redemption fee set by the fund, separate from tax — here is how it works.",
        "category": "Costs",
        "fy_label": _FY,
        "sort_order": 60,
        "source_note": "General scheme-cost explainer; specific terms are in each scheme's SID. FY 2025-26.",
        "body_md": (
            "## What an exit load is\n\n"
            "An **exit load** is a fee charged by the fund house when units are redeemed within a "
            "specified period. A common structure is **1% within 1 year** of purchase, with no "
            "load after that — but the period and rate vary by scheme.\n\n"
            "## How it is applied\n\n"
            "The load is a percentage of the **redemption value** and is deducted from the amount "
            "paid out. For example, a redemption of ₹50,000 of units that still attract a 1% load "
            "returns ₹49,500 before any tax on the gains.\n\n"
            "## It is a cost, not a tax\n\n"
            "An exit load is a **scheme cost**, not a government levy, and it is separate from "
            "capital-gains tax. The exact load for a scheme is stated in its **Scheme Information "
            "Document (SID)** and factsheet.\n\n"
            "Exit-load terms are set by each fund and change over time; check the scheme's current SID."
        ),
    },
]
