# B67 Fundamentals Data — Sourcing Decision Memo

**Status:** AMC-level slice SETTLED — **ADR-0035 (Accepted 2026-06-14)** pursues option (a) (AMFI
AMC-wise SPA → a new `amc_level_aum` field) and **deliberately leaves per-scheme `aum_crore`
source-blocked** (§8.4). OPEN founder decision for the GENUINE per-scheme slice (+ manager + credit):
**$0 ADR-0033(a) piggyback (recommended)** vs a paid data vendor — see "The $0 path" and "Open
founder decision" below.
**Date:** 2026-06-13 (updated 2026-06-14) · **Audience:** Founder · **Prepared by:** Builder
(Sonnet draft, Opus-reviewed)

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

**Update (2026-06-14).** The AMC-level slice is now settled: **ADR-0035 (Accepted)** pursues
option (a) — an AMFI AMC-wise SPA endpoint into a new `amc_level_aum` field — and explicitly leaves
per-scheme `aum_crore` source-blocked (§8.4). A **$0 path now fills that per-scheme gap:** the monthly
SEBI portfolio-disclosure files that ADR-0033(a)'s top-10-AMC constituents scraper will already parse
also carry per-scheme net assets, the current manager, and holding-level ratings — covering all three
B67 slices as a near-free add-on. It **complements ADR-0035**, it does not replace it. The single open
decision is **$0 ADR-0033(a) piggyback vs paid vendor** for that per-scheme slice — see "Open founder
decision" below.

---

## The $0 path — ADR-0033(a) piggyback (RECOMMENDED no-budget option)

**Relationship to ADR-0035.** ADR-0035 (Accepted 2026-06-14) pursues option (a) — an AMFI AMC-wise
SPA endpoint into a new `amc_level_aum` field — and is explicit that it does **not** fill per-scheme
`aum_crore`, which stays source-blocked under §8.4. The $0 path below is how that per-scheme column
actually gets filled. It **complements ADR-0035** (AMC-level context now, per-scheme `aum_crore` when
the scraper lands); it does not supersede it.

**Finding (2026-06-14).** The same monthly SEBI portfolio-disclosure files that ADR-0033(a)'s
per-AMC parsers will already read also carry, per scheme: net assets / AUM (month-end), the current
fund manager (on the scheme factsheet / SID), and holding-level credit ratings. All three B67
slices — `mf_funds.aum_crore`, the `manager_change` signal, and the debt-fund `structural_concern` —
can ride the constituents scraper as a near-free add-on. No new vendor, no new budget line, and no
additional ToS / DPDP review surface beyond what ADR-0033(a) already mandates.

**Why this satisfies §8.4.** The per-scheme net-assets line in the monthly disclosure is genuine
scheme-level data — not an AMC-aggregate imputed downward. §8.4's prohibition on deriving
`aum_crore` from AMC-level aggregate data does not apply here.

**Honest trade-offs — state all of these to the founder:**

- **Coverage is top-10 AMCs only (~75–80% of industry AUM).** Funds outside the top-10 stay an
  honest `log()`-ed gap; §8.4 forbids imputing the remainder from AMC-level totals. Same discipline
  ADR-0033(a) already imposes for constituents — no new exposure.
- **Gated on the constituents scraper delivery.** The dependency chain is Task 2 (`mf_fund_metrics`
  OOM fix) → Task 3 (scheme-master enrichment) → P2a (constituents parser). This is not a quick win;
  it arrives when the scraper arrives. (ADR-0035's AMC-level field, by contrast, can proceed on its
  own gates independently and sooner.)
- **Manager-change history accrues forward, not backward.** The current manager is available from
  snapshot 1. Change detection requires ≥2 monthly snapshots — day-1 history is not recoverable from
  this source.
- **Credit quality is derived, not curated.** We parse and weight holding-level ratings from the
  disclosure — an educational structural signal suitable for `structural_concern`. It is lower
  fidelity than a CRISIL / ICRA rating-change event feed and must not be presented as a downgrade
  alert.
- **Per-AMC format variability.** Confirm during scraper build that each of the top-10 AMCs' monthly
  disclosures prints a per-scheme net-assets line and the manager name. Near-universal on factsheets
  and portfolio statements, but format varies by AMC — verification is required before treating it
  as reliable.
- **Requires an ADR-0033 amendment.** ADR-0033(a) today scopes constituents only. Extending the
  parser to capture AUM / manager / ratings must be written up as a new ADR-0033 sub-decision — note
  that (b)/(c) are already the benchmark and redistribution decisions, so this is an ADR-0033(a)
  amendment or a fresh sub-letter — so the Tier-B / ToS / DPDP gate explicitly covers the additional
  fields. It cannot silently inherit ADR-0033(a)'s approval.

**Activation note.** Data alone does not unlock `out_of_form`. The label also requires B24 (recency
window) and B6/B28 (the two-person methodology gate). The public surface remains non-numeric and
non-advisory regardless of which data source is chosen.

## Verified vendor shortlist (route (c) — paid, deferred to revenue)

Three vendors cover all three slices and are worth quoting when revenue permits. Each needs a quote,
a counsel redistribution-terms review, and a new ADR before procurement.

- **CRISIL Intelligence** — covers per-scheme AUM, manager-change events, and agency credit ratings;
  SEBI-recognised; enterprise pricing ($$$). Highest fidelity for the credit slice.
- **ICRA Analytics MFI360** — covers all three; first-party ratings data; startup-accessible
  pricing. Already named in ADR-0033(a) as the deferred licensed constituents feed — consistent with
  the existing decision.
- **Accord Fintech ACE Datafeed** — a real REST / FTP API, India-priced. **Confirm** it carries
  per-scheme AUM **and** ratings before selecting; coverage scope needs verification.

**Skip pre-revenue:** Morningstar (~$20k+/yr), Bloomberg, LSEG — pricing is out of band for the
launch stage.

**Dead ends — do not pursue:**

- **Value Research** — no API.
- **CAMS / KFintech** — no third-party data licensing; the MFCentral third-party API shut
  September 2025.
- **`mf.captnemo.in` / `mfdata.in`** — prototyping only, not a sanctioned production source.

## Open founder decision

ADR-0035 already settled the AMC-level slice (option (a)). The remaining open question is how to
source the **genuine per-scheme** slice (per-scheme AUM + manager + credit) that ADR-0035 leaves
source-blocked.

**Single open question:** route **(d) $0 ADR-0033(a) piggyback** vs route **(c) paid data vendor**.

- **Route (d) — $0 piggyback (RECOMMENDED).** No vendor spend; no new approval surface beyond
  ADR-0033(a)'s already-mandated Tier-B / ToS / DPDP gate; all three B67 slices covered for the
  top-10 AMCs. Trade-offs: tied to constituents-scraper delivery (Task 2 → Task 3 → P2a), top-10
  coverage only, manager-change history accrues forward only, credit quality is derived. Requires an
  ADR-0033 amendment to formally extend scope.
- **Route (c) — paid vendor.** Full-universe per-scheme AUM, curated manager-change events, and
  agency-grade rating feeds — available now rather than after the scraper lands. Cost: a licensing
  fee + counsel review + an ADR per vendor. Consistent with ADR-0033(a)'s own framing: a licensed
  feed deferred until there is revenue.
- **Founder's current lean:** $0 / no-budget — consistent with ADR-0033(a)'s decision to defer the
  licensed feed. **Status: OPEN** — no decision recorded yet; this memo requests a call or async
  sign-off.
- **Either route:** `out_of_form` activation still requires B24 (recency window) + B6/B28 (the
  two-person methodology gate). Data sourcing is a prerequisite, not the sole gate. The public
  surface stays non-numeric and non-advisory regardless of source.

**Action requested:** founder to confirm **(d)** or **(c)** so the ADR-0033 amendment can be drafted
and the scraper build (or vendor procurement) sequenced.

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

1. **AUM (AMC-level) — DONE as ADR-0035.** Option (a) is settled: reverse-engineer the AMFI
   AMC-wise SPA endpoint into a new `amc_level_aum` field (honest granularity; no per-scheme
   imputation, §8.4); build gated on SPA-confirm + ToS review + data-source sanction. **For the
   GENUINE per-scheme slice (+ manager + credit) — recommended: the $0 ADR-0033(a) piggyback**
   (see "The $0 path"): ride the top-10 monthly-disclosure parsers for per-scheme AUM + current
   manager + derived credit quality; record it as an ADR-0033 amendment on the existing sanction;
   accept top-10 coverage (rest = honest `log()`-ed gap, never imputed). The paid vendor (route c)
   is the revenue-stage fallback for full-universe + curated feeds. **Decision OPEN — see "Open
   founder decision".**
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

**ADRs on record / to file:** Slice 1 option (a) is filed as **ADR-0035 (Accepted)** — AMC-level
`amc_level_aum` enrichment, §8.4 boundary, ToS-risk gate. The next ADR is an **ADR-0033 amendment**
extending the top-10 constituents scraper to also capture per-scheme AUM + manager + ratings (the $0
path) — file it once the founder confirms the $0-vs-vendor decision.

---

*All three slices need a data-source sanction (B56-f5 / Data-Ingestion discipline) — URL
liveness check + per-source ToS confirmation — before any ingestion pipeline is built.
The public surface stays non-numeric and non-advisory regardless of what is ingested.*
