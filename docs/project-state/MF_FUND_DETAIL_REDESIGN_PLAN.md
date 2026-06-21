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
- `mf_fund_metrics`: `max_drawdown_pct`, **`sharpe_ratio`, `sortino_ratio`, `volatility_pct`,
  `rolling_1y_avg_pct` / `_min_pct` / `_max_pct` / `_pct_positive`** (all computed + stored nightly,
  B74 / migration 0042), `nav_points` — all currently stripped from the API schema (need surfacing
  as **bands**, see §3.4).
- `mf_category_stats` (migration 0042): per-SEBI-category **p25/p50/p75/p90** of `return_1y_pct`,
  `return_3y_pct`, `max_drawdown_pct`. **No endpoint reads it** — it is the source for the
  "vs similar funds" bands (§3.4 / §3.6). *(Extend to also percentile the risk ratios — see §3.4.)*
- `mf_nav_history` (TimescaleDB hypertable): **full daily NAV series** — no per-fund time-series endpoint exists.
- `mf_fund_constituents` (migration 0033): top-10 holdings — `constituent_name, constituent_isin,
  sector, rating, weight_pct, market_value_cr, as_of_month`. **No endpoint reads it.**
- `fund_manager_history` (migration 0035): `manager_name, start_date, end_date`. **No endpoint reads it.**
- Scoring **contributing/contradicting signals** ("why this label") exist on the CAS-report path
  only (`FundReportItem`), not on the explorer/detail path.

**Now computed + stored (B74, PRs #282/#283 — was "not computed" in the original plan):**
rolling-1Y returns, Sharpe, Sortino, volatility (annualised std-dev), plus per-category percentiles
in `mf_category_stats`. **Still not computed:** rolling-3Y, alpha, beta (need a benchmark TRI
series). Per-fund **label/rank history** (for a trend chart) — confirm whether nightly snapshots are
persisted; if not, a small history table is required.

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
- **Rolling returns** — **rolling-1Y is now computed + stored** (`rolling_1y_avg/min/max/pct_positive`,
  B74); show fund vs category-avg as a bar/line, plus a plain summary line ("Over 1-year stretches in
  its history, results were positive most of the time" — wording from §3.4). Rolling-3Y still to
  compute. Keep numbers minimal; lead with the plain sentence.
- **Label/rank trend** (PowerUp's best idea, made compliant): plot the fund's **label trajectory**
  (`in_form…out_of_form` bands) and/or **category rank** over 6M/1Y/2Y. **No numeric scores on the
  axis** — band labels only. Requires label/rank history (see §4).

### 3.4 Risk — **metrics now BUILT (B74, PRs #282/#283); UI = band + number + help text + visual**

**Status:** `Sharpe`, `Sortino`, `volatility_pct`, and **rolling-1Y** (avg/min/max/% positive) are
**computed + stored nightly** in `mf_fund_metrics` (migration 0042), plus a `mf_category_stats`
table of per-SEBI-category percentiles. `max_drawdown_pct` was already stored. `alpha/beta` still
need a benchmark series (deferred).

**LAUNCH INSTRUCTION (founder decision 2026-06-21 — §10.6 DECIDED):** at launch, show **all three
together** for each risk metric, so a non-finance user understands it *and* a curious user sees the
real figure:

1. **Plain-language band** — the **bold headline** (the "vs similar funds" sentence). This is what a
   beginner reads first.
2. **The actual number** — shown alongside (e.g. `Sharpe 1.76`, `Volatility 14.3%`), in Geist Mono
   tabular-nums, with its **as-of date**. Factual risk numbers are **allowed** in the DOM (skill §18
   — only the proprietary score/weights/fair-value are banned, non-neg #2; **those still never
   appear**).
3. **Visual help + help text** — a small **"where this fund sits" scale** plus a one-tap
   explanation, so the number is easy to grasp without finance knowledge (detail below).

**How the band is chosen (the honest, like-for-like way):** compare the fund to **other funds in
its own SEBI category** using `mf_category_stats` percentiles — "vs similar funds", which reads as
education, not advice (skill §15 like-for-like).

**Plain-language wording (founder rule — must be understandable by a non-finance user).** Every row
is suffixed with *"(based on past performance — not a recommendation)"*:

| Metric (number shown) | Where the fund sits in its category | Plain headline shown on the page |
|---|---|---|
| Sharpe / Sortino (reward for the bumps it took) | top 25% | **"Has turned its ups-and-downs into returns better than most similar funds"** |
| | middle half | **"About average for funds like it"** |
| | bottom 25% | **"Has handled its ups-and-downs less well than most similar funds"** |
| Volatility (how much the value bounces) | least bouncy 25% | **"Steadier than most similar funds"** |
| | middle half | **"Normal ups and downs for this type of fund"** |
| | bounciest 25% | **"Bumpier ride than most similar funds"** |
| Rolling-1Y % positive (how often a 1-year hold was up) | high | **"Was up over almost every 1-year stretch in its history"** |
| | mixed | **"Has had some down 1-year stretches in its history"** |
| Max drawdown (worst drop from a peak) | shallow vs peers | **"Its worst fall was smaller than most similar funds"** (or "larger…") |

**The "make the number easy" treatment (build all of this for each metric):**

- **Headline band** (bold sentence from the table) on top.
- **The number** next to it (mono tabular + unit + "as of <date>"); colour neutral — it is a fact,
  not a verdict (never red/green "good/bad", never a 0–100 score-looking figure).
- **A position scale (the key visual):** a short horizontal track showing this fund's **SEBI-category
  range** (`p25 → p90` from `mf_category_stats`) with a **"this fund" marker** and plain-word ends —
  e.g. `Steadier ◄———●———► Bumpier`. Seeing *where the dot sits among similar funds* is what makes
  `14.3%` instantly meaningful to a beginner. (For drawdown/volatility, lower = the "good" end;
  label the ends in words, not "good/bad".)
- **One-tap help text** — a `MetricTooltip` / "What does this mean?" expander with **two plain
  sentences**: what the metric is ("how bumpy the ride was") + how to read the scale ("the dot shows
  this fund vs similar funds"). No jargon, no formulas.
- **SEBI Riskometer** (`risk_o_meter`, expose now) rendered as the SEBI gauge — regulatory + trust.
- **Insufficient data:** funds with `<252` NAV points (or near-flat NAV → metrics withheld as NULL,
  see RCA 2026-06-21) show **"Not enough history to assess risk yet"** + hide the number/scale —
  never a blank, a guess, or a misleading explosion value.

> **Backend gap to close first (small):** `mf_category_stats` today percentiles only
> `return_1y_pct / return_3y_pct / max_drawdown_pct`. To band the **risk ratios** "vs similar
> funds" **and to draw the position scale**, the nightly refresh must also percentile `sharpe_ratio`,
> `sortino_ratio`, and `volatility_pct` (just add those `metric_key`s — no schema change). The page
> needs both the fund's number AND its category `p25/p50/p75/p90` to place the marker.
>
> **Compliance note (read with §1 + skill §18):** factual risk numbers (NAV/returns/Sharpe/Sortino/
> volatility/drawdown) **MAY** be displayed — only the **proprietary score, factor weights, and fair
> value** are forbidden in the DOM (non-neg #2). So "band + number + scale" is compliant. Guardrails:
> the number is **factual, never framed as a score/verdict or a 0–100 rating**; always carries its
> **as-of date** + the past-performance / `NOT_ADVICE` disclosure; **band cut-offs + exact copy get
> Compliance (Opus) sign-off** before they ship (it is a public label surface).

### 3.5 Portfolio (data partly available)

- **Top-10 holdings** (from `mf_fund_constituents`): name, sector, rating, `weight_pct` — horizontal
  bars; "as of <month>" label. Note honestly "Top 10 of N shown" (full holdings source-blocked).
- **Sector allocation** derivable from the top-10 `sector` field (partial) — label it "by top holdings".
- **Market-cap / full sector weights:** mark **"coming soon / not yet sourced"** (do not fabricate).

### 3.6 Peers (data available)

- Peer comparison table: nearest funds in the same `sebi_category` (reuse the explorer query, a
  small slice around this fund's rank): name, label, 1Y/3Y/5Y, rank. **Educational** — no "buy #1".
- **"Vs similar funds" summary band** (from `mf_category_stats`): one plain line placing this fund in
  its category — e.g. **"Higher 3-year returns than most similar funds"** / **"Around the middle for
  funds like it"** / **"Lower than most similar funds"** — *(based on past performance, not a
  recommendation)*. Same percentile bands as §3.4; this is the single most user-meaningful, most
  compliance-safe signal because it is explicitly "compared to similar funds".

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

**B-7 — Computed metrics — ✅ DONE (B74, PRs #282/#283; box alembic 0042).** Rolling-1Y +
Sharpe/Sortino/volatility computed from NAV history, stored in `mf_fund_metrics`; per-category
percentiles in `mf_category_stats`; risk-free = `settings.RISK_FREE_RATE_ANNUAL` (6.5% proxy);
near-flat-NAV ratios withheld (`_MIN_MEANINGFUL_VOL` floor). **No scoring-input change** (these feed
no score — the two-person gate was not triggered). **Remaining B-7 work for this page:**

- **B-7a — band the metrics + expose in `FundDetail`:** add `risk_bands` (Sharpe/Sortino/vol/
  rolling/drawdown → the plain-language bands of §3.4) computed **server-side** from
  `mf_category_stats`; **the raw ratios must NOT be in the response if band-only is chosen** (§10.6).
- **B-7b — extend `mf_category_stats`** to also percentile `sharpe_ratio`, `sortino_ratio`,
  `volatility_pct` (add the `metric_key`s in the nightly refresh — no schema change) so the risk
  bands are "vs similar funds" like-for-like.
- **B-7c — alpha/beta** still deferred until a benchmark TRI series is ingested.
- **Compliance (Opus) sign-off on the band cut-offs + exact copy before they ship** (band wording
  is a public label surface).

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
- `RiskMetricCard` (per metric: **plain-language band headline + the number (mono, as-of date) +
  a `CategoryPositionScale` "this fund vs similar funds" marker + `MetricTooltip` help text**) —
  §3.4 launch treatment; consumes server-computed `risk_bands` **and** the fund's number + its
  category `p25/p50/p75/p90`. Plus `Riskometer` (SEBI gauge). The card must **never** render the
  proprietary score / weights / fair value (non-neg #2).
- `CategoryPositionScale` (reusable horizontal track: category range + "this fund" marker +
  plain-word ends) — also reused by §3.6 peers.
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

**Phase 2 — "Computed analytics."** B-7 core **already done** (Sharpe/Sortino/vol/rolling-1Y +
category percentiles stored). Remaining: **B-7a** (band + expose in `FundDetail`, server-side),
**B-7b** (extend `mf_category_stats` to the risk ratios), the **Risk section UI** (plain-language
bands per §3.4), B-8 + `LabelTrendChart`, alpha/beta once a benchmark series lands. The risk-band
copy is a public label surface → Compliance sign-off (no two-person *scoring* gate needed — these
feed no score).

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
- [ ] **Risk metrics = band headline + factual number + position scale + help text** (§3.4, §10.6
      DECIDED). Numbers are factual (allowed, skill §18); **never** framed as a score/verdict/0–100
      rating; each carries its **as-of date**. Bands computed **server-side**; band copy reviewed by
      Compliance (Opus). The proprietary **score / weights / fair value stay absent** from the DOM.
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
6. **Risk metrics — DECIDED (founder 2026-06-21): band + number + visual at launch.** Show, for each
   risk metric, the **plain-language band headline + the factual number + a "vs similar funds"
   position scale + one-tap help text** (§3.4). This is compliant (skill §18 — factual risk numbers
   allowed; only the proprietary score/weights/fair-value stay banned). Remaining sign-offs:
   **(a)** Compliance (Opus) approves the **band cut-offs + exact copy + help text** before launch;
   **(b)** confirm the number is shown free for all (not Plus-gated) — current lean: **free**, since
   it is factual and education is never paywalled (Monetization-Pricing skill).

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
  `signal-noneg2-numeric-dom`, `ui-system-typography-rollout`, `mf-risk-analytics-shipped`
  (the B74 risk metrics + the near-flat-NAV vol-floor learning).
- Risk-metric build: `backend/dhanradar/mf/risk.py`, migration `0042_mf_risk_adjusted_metrics.py`,
  `mf_metrics_refresh` in `backend/dhanradar/tasks/mf.py`; governance =
  `DhanRadar-Mutual-Fund-Analytics` skill (§7 risk metrics, §15 like-for-like category, §18 factual-
  numbers-vs-score boundary); RCA `docs/rca/README.md` (2026-06-21 Sharpe explosion).
