# UI Data Sourcing Architecture — Plan

**Status:** PLAN (not implemented). This document is the design direction; no code is
written yet.
**Date:** 2026-06-25
**Owner:** Founder + Claude Code (architect)
**Applies to:** every page in `frontend/` (Portfolio first, then all pages).
**Pairs with:** the no-suppress rule (`agent.md` → "Always render — never suppress"), the
data-ingestion governance, the scoring engine, and the SEBI non-negotiables in `CLAUDE.md`.

---

## 1. Why this plan exists

We are building UI ahead of its backends. To stay honest, robust, and lean we need a
single, repeatable way to answer three questions for **every UI component on every page**:

1. **Where does its data come from?** (a confirmed backend source — never a guess).
2. **What is its visibility class?** (public, educational, or compliance/cert-gated).
3. **Who else uses the same data?** (so one source serves many pages — no duplicates).

The result: a page that is honest today, does not break when a source is missing, gets
richer on its own as backends come online, and never fetches the same thing twice.

---

## 2. Principles (the rules every page follows)

- **Confirmed source per component.** No component ships without a named backend source.
- **One source per data concept, shared across pages.** Think by *concept* (mood, fund,
  holdings, category, flows), not by page. Each concept has exactly one owner.
- **Fail-safe.** Each component fails alone and shows a "no data" state; one missing or
  slow source never breaks the page (this is the no-suppress rule).
- **Honest.** Every value carries provenance (where it came from) and freshness (as-of).
- **Additive + scalable.** Enrichment adds new fields; it never breaks existing consumers.
  Components light up automatically as a field flips from `planned` to `live`.
- **Compliant by construction.** Visibility class, no-numeric-in-DOM (#2), educational
  labels (#1), and the disclosure bundle (#9) are decided once per concept and inherited.

---

## 3. Core model — "data concepts", not pages

A **data concept** is one owned unit of data with a single backend owner and a single
frontend access hook. Pages are *compositions* of concepts; components are *consumers* of
concepts.

```text
                         ┌────────────────────────┐
   one backend owner →   │  Concept: "mood"       │
   (service + endpoint)  │  service: mood.service │
                         │  hook: useMoodCurrent  │
                         │  visibility: public    │
                         └───────────┬────────────┘
                                     │ (one fetch, shared cache)
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                       ▼
        MoodGauge on            MoodCard on            DmmiStrip on
        /mood                   /mf/explore            /mf/portfolio
```

- **One source → many components** (fan-out reuse).
- **One page → many sources** (fan-in by composition, or a thin façade).
- **Many-to-many** between components and concepts, mediated by the shared layer.

---

## 4. The two master artifacts

The plan's deliverables are two cross-checked registries. They are the single source of
truth for "what feeds what". They start as docs and graduate to typed config in the repo.

### 4.1 Data Concept Registry (one row per concept)

| Column | Meaning |
| --- | --- |
| `concept` | stable id, e.g. `mood.current`, `holdings.list`, `fund.detail` |
| `owner_service` | the one backend module that owns the query |
| `endpoint` | the API path that exposes it (or "via façade") |
| `source_tables` | canonical table(s)/feed behind it (provenance root) |
| `status` | `live` / `partial` / `planned` |
| `visibility_class` | `public` / `educational` / `gated` |
| `gate_flag` | admin flag key (gated only); default off; which cert it needs |
| `provenance` | source system (AMFI, CAS, Yahoo, computed, …) |
| `freshness` | how `as_of` is set + expected refresh cadence |
| `consumers` | which components/pages use it (proves no duplicate source) |

### 4.2 Component Manifest (one row per UI component)

| Column | Meaning |
| --- | --- |
| `page` | route, e.g. `/mf/portfolio` |
| `section` | section name, e.g. "Holdings" |
| `component` | component name, e.g. `HoldingsTable` |
| `concepts` | which concept(s) it consumes (must exist in the Registry) |
| `state_today` | `live` / `partial` / `no-data` (drives what renders now) |
| `empty_state_copy` | the exact "no data" text shown when empty/planned |
| `compliance_note` | DOM-allowed? label/band only? disclosure required? |

**Cross-check rule:** every `concepts` value in the Manifest must exist in the Registry,
and every Registry concept must list its `consumers`. A component with no confirmed concept
cannot be built; a concept with no consumer is dead and should be removed.

### 4.3 Example rows (illustrative, to be completed during build)

Concept Registry:

| concept | owner_service | status | visibility_class | provenance |
| --- | --- | --- | --- | --- |
| `mood.current` | `mood.service` | live | public | computed from public feeds |
| `holdings.list` | `mf.portfolio_service` | live | educational | user CAS |
| `holdings.xirr` | `mf.analytics_service` | partial | educational | computed |
| `portfolio.advice` | `n/a` | planned | gated (RIA) | — |

Component Manifest:

| page | component | concepts | state_today | empty_state_copy |
| --- | --- | --- | --- | --- |
| `/mf/portfolio` | `HeroSummary` | `holdings.list` | live | "Upload your CAS to see your totals." |
| `/mf/portfolio` | `GoalTracker` | `goals.plan` | no-data | "Goal tracking is coming soon." |
| `/mood` | `InstitutionalFlowsCard` | `market.flows` | live | "No flow data yet — updates after close." |

---

## 5. The data envelope (robustness contract)

Every concept is returned in one consistent envelope so the UI always knows what to draw.
This is a *contract shape*, not code:

```text
{
  status:   "loading" | "present" | "empty" | "error" | "withheld",
  data:     <the concept payload, or null>,
  meta: {
    as_of:            ISO timestamp | null,     // freshness
    source:           "amfi" | "cas" | "computed" | ...,   // provenance
    visibility_class: "public" | "educational" | "gated",
    gate:             { flag: string, enabled: boolean } | null,
    disclaimer_version: string | null           // for educational/gated
  }
}
```

- **`withheld`** is the important new state. It means "the value exists server-side but is
  intentionally not sent": a gated dataset that is switched off, or a compliance refusal
  (e.g. confidence `< 0.30 → insufficient_data`). The UI renders the "no data / not
  available" state — it never receives the underlying number.
- **Additive + versioned.** New enrichment adds new fields or new concepts. Existing fields
  are never removed or repurposed, so old consumers keep working.

---

## 6. Visibility tiers + compliance tagging

Every concept is tagged once with a `visibility_class`; all consumers inherit it.

- **Public** — publish freely, DOM-allowed. Facts we do not compute (index, VIX, market
  levels, public flows). No restriction. (See the "public market data is DOM-allowed"
  rule.)
- **Educational** — publish freely, but **always marked**: educational label set
  (`in_form` / `on_track` / `off_track` / `out_of_form` / `insufficient_data`) plus the
  `NOT_ADVICE` + disclosure bundle. No gate, but framing is mandatory.
- **Gated (certification required)** — **hidden by default, fail-closed.** Shown only when
  an admin enables it, and only when the required certification (NISM / RIA / other) is in
  place. Advice-class data specifically needs **RIA** — the founder is an **ARN MFD
  distributor, not an adviser**, so anything that crosses the advice boundary stays gated
  until that certification exists.

**Compliance mapping (non-negotiables):** `visibility_class` + the envelope's `withheld`
state are how we enforce **#2** (no numeric score in DOM — gated/withheld never serialized),
**#1** (educational labels only), and **#9** (disclosure bundle on every educational/gated
surface).

---

## 7. Admin gating — per-page enablement

Gated data is controlled from the **admin console**, extending the existing admin flags
system (no new framework).

- **Toggle granularity: concept × page.** An admin can enable a gated concept on one page
  (e.g. Portfolio) without enabling it elsewhere. This matches "enable from admin settings
  per page".
- **Defaults:** gated = **off**; public/educational = on (educational still rendered with
  its mandatory marking).
- **Server-enforced.** When a gated concept is off for a page, the server **does not
  serialize** its data into that page's response. The UI only ever sees `withheld` and
  shows the no-data state. Hiding is never client-side only.
- **Enable preconditions (a compliance gate, not just a switch):** the certificate must be
  on file, a named approval recorded, and the in-force disclaimer version set. The toggle
  is the *mechanism*; flipping it on is a governed decision (advice-class → counsel +
  two-person sign-off).
- **Effective dating:** a gate can carry a `valid_from` date so data turns on automatically
  once a certification's effective date arrives.
- **Audit:** record who enabled what, on which page, when, against which certificate and
  disclaimer version (mirrors the `ai_recommendation_audit` pattern).

```text
Admin console → Data Visibility (per page)
┌──────────────┬────────────┬──────────┬───────────┬──────────────┐
│ page         │ concept    │ class    │ enabled?  │ cert / note  │
├──────────────┼────────────┼──────────┼───────────┼──────────────┤
│ /mf/portfolio│ advice.*   │ gated    │  OFF      │ needs RIA    │
│ /mf/portfolio│ holdings.* │ educ.    │  ON (mark)│ —            │
│ /mood        │ flows.*    │ public   │  ON       │ —            │
└──────────────┴────────────┴──────────┴───────────┴──────────────┘
```

---

## 8. Frontend architecture (dedupe in practice)

- **One shared hook per concept** in `features/<domain>/api.ts`, keyed via
  `lib/queryKeys.ts`. Components import the hook; **no component writes its own raw
  `fetch`**.
- **TanStack Query dedupes by key:** the same concept used by many components across many
  pages results in **one network call** and a shared cache.
- **Two component patterns:**
  - *Presentational* — takes typed props; the page wires the hook. Best for small reusable
    widgets (chips, gauges, bars).
  - *Connected* — calls the shared hook itself; drop-in anywhere and still deduped by
    cache. Best for self-contained sections repeated across pages.
- **Pages compose** several shared hooks, or call one thin façade hook. They never
  re-fetch raw data.
- **States are standard:** `loading` → skeleton, `present` → data, `empty`/`withheld` →
  `EmptyState` (no-suppress), `error` → inline error with retry.

---

## 9. Backend architecture

- **Service-per-concept.** One module owns each concept's query; routers are thin and call
  the service. No endpoint re-implements another's query.
- **Module isolation (#7).** Dedupe is via service interfaces, never cross-module JOINs;
  schema-per-concern is preserved.
- **Resolved once in the service layer:** provenance, freshness (`as_of`), and
  `visibility_class` for the concept — so every consumer inherits the same truth.
- **One visibility filter at the serialization boundary.** A single guard strips
  gated-off concepts (per page admin config) and replaces them with `withheld` before the
  response leaves the server. This is the one place compliance gating is enforced.
- **Optional per-page façade endpoint** that orchestrates the same services and returns a
  per-section, per-concept envelope. Keep façades thin; split them if they grow too large.
- **Caching** via Redis with explicit `as_of`; never serve a number without a freshness
  stamp.

---

## 10. Enrichment over time (scalability)

Data is layered; each layer feeds more fields without UI rework:

```text
raw holdings (CAS)  →  analytics (XIRR, returns, risk)  →  scoring (labels/bands)
                                                        →  market/AI context (mood, commentary)
```

- A new enrichment = a new concept or a new field on an existing concept (additive).
- The Manifest row flips `state_today` from `no-data`/`partial` to `live`; the component
  already mounted simply starts showing data.
- No redeploy of the page is needed for data to appear — and for gated data, no code change
  at all: an admin toggle turns it on.

---

## 11. Recommendations & best practices

- **Single source of truth per concept; ban raw `fetch` in components.** Enforce by review
  (and, optionally, a lint that flags `fetch(`/`axios` outside `features/*/api.ts`).
- **Additive-only, versioned contracts.** Never remove or repurpose a field.
- **Every field carries status + provenance + freshness.** No bare numbers.
- **Fail-closed for gated; fail-soft (show no-data) for missing.** Two different defaults
  on purpose.
- **Decide visibility once per concept**, never per page — prevents drift.
- **Keep façades thin**; prefer composition of small concepts over a mega-endpoint.
- **Contract tests:** (a) every Manifest component resolves to a real Registry concept;
  (b) a gated-off concept is never serialized; (c) the envelope shape is stable.
- **Observability:** track per-concept availability + freshness so we can see what is live
  vs stale across pages.
- **Governance:** every gate enable/disable is logged with cert + approver + disclaimer
  version; advice-class requires RIA before it can ever be enabled.

---

## 12. Phased build sequence (no code in this document)

1. **Catalogue.** Fill the Concept Registry + Component Manifest for existing pages
   (Portfolio first, then mood/explore/fund/leaderboard/calculators/dashboard).
2. **Contract.** Finalise the envelope shape + the `withheld` state + the visibility filter
   design.
3. **Dedupe.** Refactor toward one shared hook + one service per concept; remove duplicate
   sources found in step 1.
4. **Admin gating.** Build the per-page concept toggle (extend admin flags) + audit + the
   `valid_from` effective dating.
5. **Wire pages.** Connect components to shared sources; show `no-data` for `planned`
   concepts (no-suppress).
6. **Enrich.** Add analytics/scoring/market layers incrementally; components light up as
   concepts go `live`.

---

## 13. Open decisions (to settle when we execute)

- **Façade vs many hooks** per page. Lean: a thin per-page façade returning per-section
  envelopes, built from the shared services.
- **Gate granularity.** Confirmed direction: **concept × page** (per-page enablement).
- **Registry home.** Start as this doc; graduate to a typed config file in the repo so the
  contract tests can read it.
- **Decommission overlap.** As pages adopt shared concepts, retire any page-specific
  endpoints that duplicated a concept.

---

## 14. Compliance checklist (how this plan honours the non-negotiables)

- **#1 Educational boundary** — educational concepts carry the approved label set; advice
  is gated behind RIA.
- **#2 No numeric in DOM** — gated/withheld concepts are never serialized; scores stay
  server-side.
- **#9 Disclosures + audit** — educational/gated surfaces inherit the disclosure bundle and
  disclaimer version; gate changes are audited.
- **#7 Module isolation** — one service owner per concept; no cross-module JOIN.
- **No-suppress rule** — planned/empty/withheld concepts render a "no data" state; the
  component is never removed.
