# MF Fund Detail Page — Redesign & Implementation Plan

> **Status:** PLAN (for a future implementation session). Not yet built.
> **Author:** prepared 2026-06-21. **Owner of build:** next session.
> **Surface:** `/mf/fund/[isin]` — public, crawlable, no-login (PR #270). Logged-in users
> see it inside the AppShell (`MaybeShell`).
> **Tier:** A (UI) **+** Tier C touch — it renders a **score/label/AI surface**, so the
> Compliance gate applies. Backend additions to scoring-adjacent paths are **load-bearing**.

---

## 0. Why this doc exists

The live fund detail page (`frontend/src/app/mf/fund/[isin]/page.tsx`) is thin: header, a
LabelChip, two return cards, an AMC-AUM card, an Upload-CAS CTA, and the disclosure bundle.
It also has **no dedicated single-fund API** — it paginates the Fund Explorer list endpoint
until it finds the ISIN. We want a **best-in-class, interactive, all-in-one-page** fund detail
experience, informed by:

- the **ui-system master** (`docs/ui-system/` — screens/`fund-detail.md`, `html/hifi-screens.html`,
  component + brand specs);
- **PowerUp Money** reference screens (`docs/Sample/fund details/*.jpeg`);
- **competitor best practice** (Tickertape, Groww, INDmoney, Kuvera, Value Research, Morningstar,
  Zerodha Coin, ET Money).

This plan turns that research into a concrete, **compliance-correct**, phased build.

---

## 1. Binding compliance constraints (read first — these override every design idea)

The reference material is full of advisory/numeric patterns we **must not copy**. Per the project
non-negotiables:

| # | Rule | What it forbids on this page |
|---|------|------------------------------|
| 1 | **SEBI educational boundary** | No buy/sell/hold/"Strong Buy"/"Great to Invest"/"pause"/"exit" anywhere. Only the label set `in_form / on_track / off_track / out_of_form / insufficient_data`. |
| 2 | **No numeric in DOM** | No raw score (the mockup's **`92`**), no factor weights, no fair value, no proprietary 0–100 sub-scores (PowerUp's "Consistency 90/100"). |
| 4 | **Confidence band only** | `high / medium / low`; `< 0.30 → insufficient_data` (refuse). |
| 6 | **Tier-gating = 402** | Premium-only panels gate server-side, never leak numerics to the client. |
| 9 | **Disclosures + audit** | Every score/label/AI surface renders the disclosure bundle + `NOT_ADVICE`. |

**Translation table — copy the data richness, drop the advisory framing:**

| Reference feature (do NOT copy verbatim) | DhanRadar compliant equivalent |
|---|---|
| Mockup `ScoreRing` showing **`92`** | Ring renders a **confidence band as a colour arc only**, *no number in the DOM*; pair with `LabelChip`. |
| Mockup badge **"● Strong Buy"** | `LabelChip` (`in_form`…) + a **descriptive** sub-line ("Among top performers in its category, historically"). Never an action verb. |
| PowerUp "Power Rank 4/10", "Consistency 90/100", "Recency 91/100" | **Category rank ordinal** `#N of M` (a rank, not a score — already permitted) + **confidence band**. No 0–10 / 0–100 numbers. |
| PowerUp "Great to Invest / Start SIP", "See why ▶" → invest advice | "See why" → **explain the label rationale** (contributing/contradicting signals) as education, never "invest now". |
| Star ratings (Morningstar/VRO/Groww) | Educational label + band; optionally the factual **percentile/rank** within category. No stars. |
| ET Money "Fund Verdict / fit for you" | Educational **"how to read this" / fit checklist** that shows facts and lets the user judge; no verdict. |
| **"Invest" / "Withdraw" / "Start SIP — ₹500/mo"** CTAs (mockup + PowerUp) | **No transaction CTAs.** Use **"Add to Watchlist"** + **"See this fund in your portfolio → Upload CAS"**. (Wiring real transactions flips us to a distribution-platform posture — ARN/MFD conflict & commission disclosure, counsel + founder gate. Out of scope here.) |
| PowerUp label set used as advice (project memory: PowerUp is the in-market copycat-risk competitor) | Same labels, **descriptive** framing only. Before any *new* public label-trend surface, keep the existing copy reviewed by Compliance. |

**The label is rule-table-derived, not a pure function of the score (non-neg #1). The risk
profile must never feed the score (#3).**

---

## 2. Current state (what we build on)

**Frontend** — `frontend/src/app/(app)/mf/fund/[isin]/page.tsx` renders: back-link, header
(category eyebrow + scheme name + AMC), assessment card (`LabelChip` + plan/option chips), rank
`#N of M`, two `ReturnCard`s (1Y/3Y), conditional AMC-AUM card, Upload-CAS CTA, `DisclosureBundle`.
Compliance is currently **clean** (no numeric/advisory/fair-value). `ScoreRing` is imported for
types only — **not rendered**.

**Data resolution** — via `useFundDetail` (`frontend/src/features/mf/api.ts`) hitting the
**paginated** `GET /api/v1/mf/funds` (no single-fund route). Schema = `FundExplorerItem`
(`backend/dhanradar/mf/schemas.py`).

**Available now** (per `FundExplorerItem`): `isin, scheme_name, amc_name, sebi_category,
plan_type` (partial), `option_type` (partial), `verb_label`, `category_rank`, `category_total`,
`return_3m/6m/1y/3y/5y_pct`. `confidence_band` and `confidence_factors` are **hard-coded null** in
the router (need wiring). `amc_level_aum_crore` is hard-coded null.

**In the DB but NOT exposed by any API** (cheap to surface — *data already exists*):

- `mf_funds`: `benchmark_index`, `risk_o_meter`, `launch_date`, `sub_category`,
  `expense_ratio_pct` / `exit_load_pct` *(columns exist but are **always NULL** — no ingest path)*.
- `mf_fund_metrics`: `max_drawdown_pct` (computed, stored, but stripped from the schema), `nav_points`.
- `mf_nav_history` (TimescaleDB hypertable): **full daily NAV series** — no per-fund time-series endpoint exists.
- `mf_fund_constituents` (migration 0033): top-10 holdings — `constituent_name, constituent_isin,
  sector, rating, weight_pct, market_value_cr, as_of_month`. **No endpoint reads it.**
- `fund_manager_history` (migration 0035): `manager_name, start_date, end_date`. **No endpoint reads it.**
- Scoring **contributing/contradicting signals** ("why this label") exist on the CAS-report path
  only (`FundReportItem`), not on the explorer/detail path.

**Not computed anywhere** (needs new backend work): rolling returns, Sharpe, Sortino, std-dev,
alpha, beta. Per-fund **label/rank history** (for a trend chart) — confirm whether nightly
snapshots are persisted; if not, a small history table is required.

**Source-blocked** (per memory/ADRs — do not fake): **scheme-level AUM** (ADR-0035 settled on
AMC-level; per-scheme blocked), **expense ratio / exit load** (no ingest source), **full holdings
beyond top-10** and **full sector/market-cap weights** (only top-10 constituents are sourced today).

---

## 3. Target page architecture

Layout follows the ui-system master: **a sticky in-page sub-nav + long scroll** (the highest-impact
nav win the competitor research found that *no Indian platform does well*). Desktop = two-column
where the master shows it; mobile = single column, sticky sub-nav becomes a horizontal scroller,
secondary CTA sticky at bottom.

**Section order (top → bottom):**

### 3.1 Header / identity (always)

- AMC token (`.tk-logo`), scheme name (`text-h2`/26px Geist Sans 700, `-0.025em`), sub-line
  `sub_category · plan_type · option_type · AMC` (mono caption), breadcrumb `Mutual Funds › <category>`.
- **NAV** + as-of date + 1D change (mono, tabular-nums; emerald/red by sign) — from latest `mf_nav_history`.
- **Right of header:** `LabelChip` (label + confidence band) + **confidence ring (band arc, NO number)** +
  `#N of M in <category>`. **No "Start SIP" button.** Replace with **"Add to Watchlist"** (secondary)
  and a quiet **"Upload CAS to see this in your portfolio"** link.
- **Data-freshness chip** ("NAV as of …", "Holdings as of <month>") — trust pattern, universal in research.

### 3.2 Sticky sub-nav (anchor links)

`Overview · Performance · Risk · Portfolio · Peers · Fund info · Manager · Tax · FAQs` — fixes to
top on scroll, jump-scrolls to anchors. Hidden sections (no data) are omitted, not shown empty.

### 3.3 Performance

- **NAV chart** (`AreaChart`, ui-system `Chart`) with range toggles **1M·3M·6M·1Y·3Y·5Y·Max**;
  overlay **benchmark line** when `benchmark_index` series is available (Kuvera-style). Positive trend = emerald.
- **"Growth of ₹10,000"** view toggle on the same chart (derive from NAV series) — the single best
  trust device per research. Educational framing ("had you tracked ₹10,000…"), not a projection.
- **Trailing returns table** — periods 3M/6M/1Y/3Y/5Y (have now) vs **category average** and
  **benchmark** (when available); CAGR, mono tabular. `—` for suppressed young-fund periods (honesty).
- **Rolling returns** (Phase 2 compute) — 1Y/3Y rolling, fund vs category-avg; bar/line.
- **Label/rank trend** (PowerUp's best idea, made compliant): plot the fund's **label trajectory**
  (`in_form…out_of_form` bands) and/or **category rank** over 6M/1Y/2Y. **No numeric scores on the
  axis** — band labels only. Requires label/rank history (see §4).

### 3.4 Risk (Phase 2 compute)

- `max_drawdown_pct` (expose now), **Sharpe, Sortino, std-dev** (compute from NAV), **alpha/beta**
  (need benchmark series). Each with an **inline plain-language tooltip** ("higher Sharpe = better
  risk-adjusted return") — research shows tooltips are a top trust pattern.
- **SEBI Riskometer** (`risk_o_meter`, expose now) rendered as the SEBI gauge — regulatory + trust.

### 3.5 Portfolio (data partly available)

- **Top-10 holdings** (from `mf_fund_constituents`): name, sector, rating, `weight_pct` — horizontal
  bars; "as of <month>" label. Note honestly "Top 10 of N shown" (full holdings source-blocked).
- **Sector allocation** derivable from the top-10 `sector` field (partial) — label it "by top holdings".
- **Market-cap / full sector weights:** mark **"coming soon / not yet sourced"** (do not fabricate).

### 3.6 Peers (data available)

- Peer comparison table: nearest funds in the same `sebi_category` (reuse the explorer query, a
  small slice around this fund's rank): name, label, 1Y/3Y/5Y, rank. **Educational** — no "buy #1".

### 3.7 Fund info (mix)

- Now: `benchmark_index`, `launch_date`/age, `sub_category`, `min_sip` (if available), riskometer.
- Source-blocked, show as "not yet sourced": `expense_ratio`, `exit_load`, scheme-level AUM
  (show AMC-level when present, with the existing caveat).

### 3.8 Fund manager (data available — `fund_manager_history`)

- Manager name(s) + tenure (start/end). Optional drill-down later (other funds managed) — Phase 3.

### 3.9 Tax (no data needed — static rules)

- Equity STCG/LTCG rules + ₹1.25L LTCG exemption note (educational, current FY rules), as a static
  explainer. **No personalised tax estimate** (that needs holdings/transactions = distribution posture).

### 3.10 "Why this label" (Tier-C, high value)

- Surface the scoring **contributing/contradicting signals** as plain-language bullets (already exist
  on the CAS path). Make the label explainable. **Bands/labels only, no numerics.** Compliance-gated.

### 3.11 FAQs (SEO + education)

- Auto-generated expandable Q&A (NAV, returns, holdings, what the label means, ratio definitions) —
  native `<details>`/`<summary>` (crawlable, matches the existing landing FAQ pattern).

### 3.12 Footer

- `DisclosureBundle` + `NOT_ADVICE` + methodology link (`/methodology`) + data-freshness/provenance.

---

## 4. Backend work required

> All of this is **load-bearing / scoring-adjacent → full inline Tier-B/C review + gates in the
> session it lands** (Security/Compliance sign-off; `codex:rescue` is unavailable on this account →
> Sonnet adversarial takeover per memory).

**B-1 — Dedicated single-fund endpoint** `GET /api/v1/mf/fund/{isin}` returning a new
`FundDetail` schema (superset of `FundExplorerItem`). Stop paginating the list client-side. Public,
no-auth, RFC7807 errors, `request_id`. **Server must continue to exclude the raw `unified_score`.**

**B-2 — Expose existing-but-hidden fields** in `FundDetail`: `benchmark_index, risk_o_meter,
launch_date, sub_category, max_drawdown_pct`. Wire **`confidence_band`** (currently hard-null) from
the ranks/scoring output; if not stored, compute+store it (band only).

**B-3 — NAV history endpoint** `GET /api/v1/mf/fund/{isin}/nav?range=1m|3m|6m|1y|3y|5y|max`
returning a downsampled time-series from `mf_nav_history` (TimescaleDB). Powers the NAV chart and
"Growth of ₹10,000". Add benchmark series when sourced.

**B-4 — Holdings endpoint** `GET /api/v1/mf/fund/{isin}/holdings` from `mf_fund_constituents`
(top-10 + `as_of_month`). Derive partial sector allocation server-side.

**B-5 — Manager endpoint / inline** from `fund_manager_history`.

**B-6 — Peers slice** `GET /api/v1/mf/fund/{isin}/peers` (or include in B-1) — N funds around this
fund's category rank.

**B-7 — Computed metrics (Phase 2):** rolling returns + Sharpe/Sortino/std-dev from NAV history;
alpha/beta once a benchmark series exists. Store in `mf_fund_metrics` (extend) via the nightly
pipeline. **Methodology two-person gate applies to any scoring-input change.**

**B-8 — Label/rank history (for §3.3 trend):** confirm whether nightly label/rank snapshots persist;
if not, add a `mf_fund_label_history` (fund, as_of_month, label, confidence_band, category_rank).
Backfill is not possible — accrues forward, so ship the trend chart "from <first-snapshot month>".

**Do NOT** invent: scheme-level AUM, expense ratio, exit load, full holdings, full sector/market-cap
weights. Render these as explicit "not yet sourced" states.

---

## 5. Frontend work required

New components under `frontend/src/components/mf/` (reuse ui-system `Card`, `Chart`, `Table`,
`LabelChip`, `Skeleton`; tokens only — never hand-edit generated token files):

- `FundDetailHeader` (identity + NAV + label + **band ring, no number** + watchlist CTA + freshness).
- `FundSubNav` (sticky anchor nav; horizontal scroll on mobile).
- `NavChart` (area chart + range toggle + benchmark overlay + ₹10,000 toggle).
- `TrailingReturnsTable` (fund vs category-avg vs benchmark; mono tabular; `—` for suppressed).
- `RollingReturnsChart` (Phase 2).
- `LabelTrendChart` (band trajectory — **no numeric axis**) (Phase 2 / needs B-8).
- `RiskRatios` (cards + inline tooltips) + `Riskometer` (SEBI gauge).
- `HoldingsPanel` (top-10 bars + partial sector tab + "top 10 of N" honesty).
- `PeerComparisonTable`.
- `FundInfoGrid` (+ "not yet sourced" states).
- `FundManager`.
- `TaxExplainer` (static), `WhyThisLabel` (signals), `FundFaq` (`<details>`).
- A reusable `MetricTooltip` (plain-language definitions — founder rule: simple words for non-experts).

Update `useFundDetail` to call B-1; add hooks for B-3..B-6. Mark premium-only panels with a
**402-aware** upsell stub (no numeric leak).

All numbers render in **Geist Mono, tabular-nums**; type scale + colours from tokens; positive=emerald,
negative=red, primary=royal `#1E5EFF`. Mobile: single column, 44px tap targets, sticky secondary CTA.

---

## 6. Phasing (ship value early; never block on source-blocked data)

**Phase 1 — "Rich page from data we already have" (no new sourcing).**
B-1, B-2, B-3 (NAV chart + ₹10k), B-4 (top-10 holdings + partial sectors), B-5 (manager), B-6
(peers). Frontend: header (band ring), sub-nav, NAV chart, trailing returns vs category, holdings,
peers, fund info (with honest gaps), manager, tax explainer, FAQs, why-this-label. **This alone is a
night-and-day upgrade.**

**Phase 2 — "Computed analytics."** B-7 (rolling returns + Sharpe/Sortino/std-dev), B-8 +
`LabelTrendChart`, risk section, alpha/beta once benchmark series lands. Two-person methodology gate.

**Phase 3 — "Blocked-on-source / premium."** Scheme-level AUM, expense ratio, exit load, full
holdings + full sector/market-cap weights (need an ingest source — sequence behind the ADR-0033
constituents scraper extension, see memory `b67-aum-no-clean-per-scheme-source`). SIP/lumpsum
calculator (client-side, can be earlier). Manager drill-down. Tier-gated deep analytics.

---

## 7. Interactivity spec (the "interactive, all-in-one" ask)

- NAV chart **range toggles** + **benchmark overlay** + **₹10,000 growth** toggle.
- **Returns view switcher:** Trailing / Rolling / (Calendar-year later).
- **Sticky sub-nav** jump links; **progressive disclosure** (expand holdings, "see all peers",
  expand "why this label").
- **Inline metric tooltips** on every ratio/term (plain language).
- **Add to Watchlist** toggle; **peer "compare"** link into the existing compare flow.
- **SIP/lumpsum return calculator** (Phase 3, client-side from returns/NAV) — outputs invested vs
  value vs return %, **clearly framed as historical illustration, not a projection or advice**.

---

## 8. Compliance & disclosures checklist (gate before merge)

- [ ] No numeric score / weight / fair value in DOM (grep). Ring = **band arc only**.
- [ ] Only the 5 educational labels; **no advisory verbs** anywhere (grep `strong_buy|buy|sell|hold|caution|avoid` + "Start SIP/Invest/Withdraw").
- [ ] Confidence band-only; `< 0.30 → insufficient_data`.
- [ ] Risk profile never feeds the score; scoring inputs unchanged unless two-person gated.
- [ ] `DisclosureBundle` + `NOT_ADVICE` rendered; methodology link present; data-freshness shown.
- [ ] Premium panels gate **server-side** (402), no numeric leak to client.
- [ ] No transaction CTA (distributor posture deferred; counsel + founder gate).
- [ ] PowerUp label-collision risk reviewed (memory `powerup-money-label-collision`) before any new
      public label-trend surface.

**Deterministic gates:** ruff/mypy/tsc · `next lint` · `next build` · anti-pattern + advisory-verb +
no-numeric greps · backend tests in CI (CI is the gate, not local). **Reviews:** Tier-C inline
(Compliance Opus + Product) for the score/label surface; Security (Sonnet adversarial) for new
endpoints; per-change review file under `docs/project-state/reviews/`.

---

## 9. Acceptance criteria

1. `GET /api/v1/mf/fund/{isin}` returns the `FundDetail` superset; page no longer paginates the list.
2. NAV chart renders real `mf_nav_history` with working range toggles + ₹10,000 view.
3. Trailing returns shown vs category average (and benchmark when available); suppressed periods show `—`.
4. Top-10 holdings + manager + peers render from real DB data with "as of" dates.
5. Label + confidence **band** shown with **no number**; ring is a band arc.
6. All numbers Geist Mono tabular; tokens-only styling; mobile single-column with sticky sub-nav.
7. Compliance checklist §8 fully green; all gates pass in CI.
8. Source-blocked fields show explicit "not yet sourced", never fabricated values.

---

## 10. Open questions / decisions for the founder

1. **Watchlist vs transactions** — confirm CTA is "Add to Watchlist" + "Upload CAS" only (no Invest/SIP)
   until the distribution-platform decision (ARN/MFD conflict disclosure) is taken with counsel.
2. **Label-trend chart** — OK to ship "from first snapshot month" (no backfill possible)? Approve adding
   `mf_fund_label_history`.
3. **Premium gating** — which deep-analytics panels (rolling returns? risk ratios? peers?) are Plus-only
   vs free? (Monetization-Pricing skill governs; safety/education never paywalled.)
4. **Sourcing budget** — green-light the ADR-0033 scraper extension for expense ratio / full holdings /
   sector weights, or keep them "not yet sourced" for now?
5. **PowerUp label collision** — counsel trademark check before a *new* public label-trend surface?

---

## 11. Source references

- ui-system: `docs/ui-system/screens/fund-detail.md`, `etf-detail.md`; `docs/ui-system/html/hifi-screens.html`
  (the "Mutual Fund Detail" screen — note its non-compliant `92` + "Strong Buy" to be fixed);
  `docs/ui-system/components/{Chart,Card,Table}.md`; `docs/ui-system/brand/README.md`.
- PowerUp reference: `docs/Sample/fund details/*.jpeg` (HDFC NIFTY Smallcap 250 Index — full content
  inventory captured; advisory elements flagged not-to-copy).
- Current impl: `frontend/src/app/(app)/mf/fund/[isin]/page.tsx`, `frontend/src/features/mf/api.ts`,
  `backend/dhanradar/mf/{router,schemas,models}.py`; tables `mf_funds`, `mf_fund_metrics`,
  `mf_fund_ranks`, `mf_nav_history`, `mf_fund_constituents` (0033), `fund_manager_history` (0035).
- Competitor research (accessed 2026-06-21): Tickertape, Groww, INDmoney, Kuvera, Value Research,
  Morningstar, Zerodha Coin, ET Money — section checklist, interactivity, all-in-one patterns,
  advisory-boundary flags (full citations in the research log; key idea = sticky sub-nav + ₹10k
  growth overlay + inline tooltips + rolling returns, minus stars/verdicts/scores).
- Authority: `docs/DhanRadar_Architecture_Final.md`, `FINAL_SCORING_SPEC.md`, project `CLAUDE.md`
  non-negotiables; memories `powerup-money-label-collision`, `b67-aum-no-clean-per-scheme-source`,
  `signal-noneg2-numeric-dom`, `ui-system-typography-rollout`.
