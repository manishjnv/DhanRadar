# G8 Tax-Education — figure verification (FY 2025-26 / AY 2026-27)

**Date:** 2026-06-10 · **Verified by:** AI evidence-gathering from authoritative sources
(AMFI, ClearTax, TaxGuru, official rate notes). **Status of each figure below: CONFIRMED or
CORRECTED.**

> ⚠️ **This is AI-gathered corroborating evidence, not a Chartered Accountant's sign-off.**
> It catches factual errors against public authoritative sources and substantially de-risks
> the content, but a practising CA's dated written confirmation is still recommended for
> legal cover before the `noindex` is removed and the pages are published to search.

## Result

Two errors were found and **corrected in `content.py`** (and reseeded to prod); the rest
were confirmed correct.

| # | Claim in the content | Verdict | Authoritative source(s) |
|---|---|---|---|
| 1 | Equity-oriented fund = ≥65% in domestic equity | ✅ confirmed (direct-fund limb; a fund-of-funds limb uses ≥90%) | AMFI Tax Regime page; IT Act §112A Explanation |
| 2 | Equity **STCG 20%** (§111A), held ≤12m | ✅ confirmed (raised 15%→20%, transfers on/after 23 Jul 2024) | AMFI; PL Capital; Tax2win §112A |
| 3 | Equity **LTCG 12.5%** over **₹1.25L**/FY, no indexation, held >12m (§112A) | ✅ confirmed (rate 10%→12.5%, exemption ₹1L→₹1.25L) | AMFI; ManipalCigna/Bajaj §112A |
| 4 | **Specified mutual fund** definition | ❌→✅ **CORRECTED**: was "≤35% equity"; the FY 2025-26 / AY 2026-27 definition (Finance Act 2024) is **">65% in debt & money-market instruments"** | AMFI FY 2025-26 Tax Regime page; TaxGuru §50AA amendment; ClearTax §50AA |
| 5 | Specified-fund gains at **slab rate**, short-term, units acquired on/after **1 Apr 2023** (§50AA) | ✅ confirmed | TaxGuru; ClearTax §50AA |
| 6 | Pre-1-Apr-2023 debt: LTCG (>36m) **12.5% no indexation** on transfers on/after 23 Jul 2024; STCG at slab | ✅ confirmed | Finance Act 2024 capital-gains rules |
| 7 | **ELSS** 3-yr lock-in **per instalment** | ✅ confirmed | ClearTax ELSS lock-in; Aditya Birla |
| 8 | **§80C** ₹1.5L/FY, **old regime only** (new/default regime disallows 80C) | ✅ confirmed | IndianTaxPlanning §80C FY 2025-26; TaxTMI |
| 9 | **IDCW** taxed at slab; **§194K TDS 10%** | ✅ rate confirmed | Finnovate; TaxBuddy §194K |
| 10 | §194K **TDS threshold** | ❌→✅ **CORRECTED**: was **₹5,000**; for FY 2025-26 it is **₹10,000** (raised w.e.f. 1 Apr 2025) | ClearTax §194 (threshold ₹5,000→₹10,000 w.e.f. 1 Apr 2025); Sundaram Tax Reckoner 2025-26 |
| 11 | Advance tax 15 Jun / 15 Sep / 15 Dec / 15 Mar (15/45/75/100%) | ✅ confirmed | ClearTax/Tax2win due-date guides AY 2026-27 |
| 12 | ITR due date (non-audit individuals) **31 Jul** 2026 | ✅ confirmed | ClearTax/Tax2win AY 2026-27 |
| 13 | Exit load — a scheme fee, not a tax | ✅ not a tax-law claim (per the scheme SID) | — |

## Corrections applied (`content.py`, reseeded 2026-06-10)

1. **§194K threshold ₹5,000 → ₹10,000** (IDCW article summary + body; raised by Finance Act
   2025 w.e.f. 1 Apr 2025). `_SRC` now also cites the Finance Act 2025.
2. **Specified-fund definition → ">65% in debt & money-market instruments"** (debt article +
   the basics-article hybrid line), with a note that the Finance Act 2024 narrowed the older
   "not more than 35% equity" test from AY 2026-27 (some ETFs / gold funds / 35–65% hybrids
   are no longer specified funds).

## Residual items a human CA should still confirm

- The **exact effective-date reading** for the §50AA redefinition (sources phrase it as both
  "FY 2025-26" and "from 1 April 2026 / AY 2026-27" — AMFI's own FY 2025-26 page uses the new
  definition; a CA should confirm the transfer-date the new definition binds).
- The treatment of the **35–65% "middle" funds** (legislative silence — the content now points
  to "residual capital-gains rules"; a CA should confirm the precise rate/holding period).
- Whether any **Budget 2025** change beyond §194K affects these figures.

Sources were read on 2026-06-10; tax law changes yearly — re-verify before each FY.
