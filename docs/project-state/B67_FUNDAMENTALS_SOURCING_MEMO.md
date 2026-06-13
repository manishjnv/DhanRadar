# B67 Fundamentals Data — Sourcing Decision Memo

**Status:** Decision required before any build work begins (no code written yet).
**Date:** 2026-06-13 · **Audience:** Founder · **Prepared by:** Builder (Sonnet draft, Opus-reviewed)

---

## Summary

All three "fundamentals" slices — per-scheme AUM, manager change, and credit
downgrades — are currently **source-blocked**. None is a quick win. The 2026-06-13
source recon corrected an earlier premise: AUM is not sequence-first or easily
sourced; AMFI's restructured site eliminated the legacy endpoints DhanRadar would
have relied on. Manager change has no clean free feed. Credit downgrades require a
licensed rating-agency relationship. Recommendation: defer AUM to a bounded
**AMC-level** signal (new field, no imputation), park manager change pending a vendor
cost assessment, and treat credit downgrades as a counsel-gated future slice. No
slice is built before its ADR is filed and a data-source sanction is obtained.

---

## Slice 1 — Per-scheme AUM (`mf_funds.aum_crore`, empty today)

**What changed (2026-06-13 recon):**

- AMFI migrated to Next.js + Strapi. Every legacy endpoint (`modules/AverageAUMDetails`,
  `spages/aaum*.aspx`, `Themes/.../AverageAUM.aspx`) returns 404.
- Current `/aum-data/*` pages (average-aum, classified-average-aum, aum-disclosure)
  serve **AMC-wise** (fund-house-level) average AUM via a client-side SPA call — no
  static extractable file; the page is a directory of per-AMC links to each AMC's site.
- KVM4 is **not** geo-blocked from AMFI (HTTP 200). The wall is granularity + endpoint
  reverse-engineering, not reachability.
- No currently-identified AMFI endpoint publishes **per-scheme** AUM.

**Hard constraint:** Data-Ingestion §8.4 forbids imputing per-fund `aum_crore` from
AMC-level aggregate data. This rules out the obvious apparent shortcut.

**Option (a) — Reverse-engineer the AMFI SPA AMC-level endpoint → a NEW AMC-level field.**

- Feasibility: moderately plausible (the SPA call is visible in dev tools), but AMFI
  tightened fintech data access Sep-2025 → ToS risk on an undocumented endpoint.
- Signal: AMC-level only — fund-house size/flow context, a weaker fund-level signal.
- Cost: engineering only (endpoint RE + normalization + breakage monitoring); no
  licensing. Gates: ToS legal confirmation + data-source sanction + ADR.
- Does **not** fill the per-scheme `aum_crore`; needs a new `amc_level_aum` field with
  honest granularity labelling.

**Option (b) — Scrape 40+ AMC monthly factsheets / portfolio disclosures.**

- Feasibility: possible but a large normalization project (heterogeneous PDF/Excel/HTML
  per AMC). Sep-2025 tightening raises ToS risk across the board.
- Signal: per-scheme (the right granularity); quality depends on AMC disclosure.
- Cost: large + ongoing maintenance; per-AMC ToS review + data-source sanction + ADR;
  counsel should advise on aggregated scraping. Multi-sprint; not before governance.

**Option (c) — License a paid data vendor (per-scheme AAUM).**

- Feasibility: vendors exist; unverified which cover per-scheme AAUM at scheme level.
- Signal: per-scheme, highest quality if AMFI-sourced.
- Cost: **licensing cost unknown — needs a vendor quote**; counsel review of
  redistribution terms. Gates: vendor selection + licensing + counsel + ADR.

**What AUM unlocks:** size/flow context (large vs boutique; inflow/outflow trends).
Useful enrichment — **not** currently required by any label in the live rule table.

---

## Slice 2 — Manager change

**State:** the `manager_change` signal is wired into `scoring_bridge.py` / `labels.py`
but has **no data writer** → the `out_of_form` path that depends on it is unreachable.

- Source candidates: per-AMC SID / monthly factsheets disclose the manager; change
  detection needs historical scraping + structured diffing (ToS risk, Sep-2025 context).
  No clean free structured feed identified. Paid vendors may carry curated
  manager-change events — unverified, cost unknown.
- Gates even with data: activating `out_of_form` also needs **B24** (recency window) +
  the **two-person methodology gate (B6/B28)**. Data alone does not unlock the label.

**Decision needed:** accept `out_of_form` as partially unreachable at launch and revisit
later, OR commission a vendor assessment now. A source decision precedes the ADR; the
ADR precedes any build.

---

## Slice 3 — Credit downgrades

**State:** no writer, no source. Relevant to debt-category funds (structural risk).

- Source candidates: CRISIL / ICRA / CARE rating-change events — all licensed/commercial;
  no free structured rating-change feed identified; direct API needs a commercial deal.
- Gates: licensing + counsel (redistribution + disclosure obligations on rating data) +
  ADR. The highest-gating slice.

**What it unlocks:** debt-fund structural-risk input to `out_of_form`.

---

## Recommendation

**Sequencing for the founder's decision:**

1. **AUM — pursue option (a) only, bounded scope.** Reverse-engineer the AMFI SPA
   endpoint for **AMC-level** AUM into a NEW AMC-level field; do **not** impute
   per-scheme (§8.4 is hard). File an ADR scoping it as AMC-level enrichment, recording
   the ToS-risk decision; get ToS legal confirmation before ingestion. Most tractable
   near-term action.
2. **Manager change — commission a vendor cost assessment before the next phase.** Do not
   build SID/factsheet scraping without a ToS opinion (Sep-2025 tightening). If vendor
   cost is acceptable, file the ADR; otherwise explicitly defer and accept `out_of_form`
   partial unreachability via this pathway at launch.
3. **Credit downgrades — defer; counsel gate is non-negotiable.** Do not approach rating
   agencies without counsel. Post-launch unless an existing relationship exists.

**Explicit do-nots:**

- Do not impute `aum_crore` from AMC-level data (§8.4). Column stays empty until a
  per-scheme source is sanctioned.
- Do not scrape AMC factsheets for manager change without per-source ToS review + a
  data-source sanction.
- Do not activate the `out_of_form` credit pathway without a licensed feed and the
  methodology gate cleared (B6/B28).
- Do not treat any slice as a "quick fill" — the recon confirms none is.

**First ADR to file:** Slice 1 option (a) — scope AMC-level AUM as a new enrichment
field, document the §8.4 boundary, record the ToS-risk decision.

---

*All three slices need a data-source sanction (B56-f5 / Data-Ingestion discipline) — URL
liveness check + per-source ToS confirmation — before any ingestion pipeline is built.
The public surface stays non-numeric and non-advisory regardless of what is ingested.*
