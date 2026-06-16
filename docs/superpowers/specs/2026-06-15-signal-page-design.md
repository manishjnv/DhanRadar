# Signal Page — Design Specification

**Date:** 2026-06-15
**Status:** Approved for implementation planning
**Mockup:** `.superpowers/brainstorm/1679-1781526107/content/signal-v3.html`

---

## 1. Overview

Signal is a new protected page (`/signal`) in the DhanRadar app that gives logged-in investors
a personal rule-based market check. It combines three concerns in one destination:

1. **Today** — Live market signals (Nifty 50, India VIX, Market Breadth) checked against the
   user's own configured thresholds. Shows whether their pre-decided rules are triggered.
2. **Rules & Fund** — Configuration of signal thresholds, dip fund capital tracking, and
   deployment ladder settings.
3. **Reflect** — Investment journal, behaviour analytics, trust engine, and gamification.

### Goals

- Remove emotional decision-making by surfacing whether the user's own rules say "now" or "wait."
- Protect SIP discipline: reinforce that SIPs continue regardless of market conditions.
- Protect dip fund capital: staged deployment ladder prevents going all-in on a single signal.
- Build investing discipline over time via journaling, scores, and trust-engine feedback.
- Provide contextual learning content alongside market signals.

### Non-goals

- Signal does **not** recommend specific funds or stocks.
- Signal does **not** predict market direction.
- Signal does **not** replace or override the user's own judgement.

---

## 2. SEBI Compliance

Signal is SEBI-educational, not advisory. Every surface must honour these invariants
(see `CLAUDE.md` §Non-negotiables):

| Rule | Implementation |
|---|---|
| No advisory verbs (`buy`/`sell`/`hold`) | Signal outputs: **Triggered / Watch / No signal** — never "Invest/Sell/Hold" |
| No numeric DhanRadar score in DOM | Behaviour scores (Investor/Discipline/Patience) are user-behaviour metrics, not fund scores — display as integer 0–100 |
| Disclosure on every AI/signal surface | `NOT FINANCIAL ADVICE` line in every signal hero card footer |
| Trust Engine disclaimer | "Past accuracy does not predict future outcomes. Educational context only." always shown |
| No buy/sell on specific instruments | Learning content links to `/learn/` pages; never a fund CTA from a signal |

---

## 3. UI Design Consistency — Mandatory Rule

> **Before any UI change, new component, or screen on this page or anywhere else in
> DhanRadar, the implementer MUST reference:**
>
> - `docs/ui-system/html/dhanradar-design-system.html` — canonical component markup, class
>   names, exact CSS patterns, and visual motifs.
> - `docs/ui-system/components/` — per-component specs (Button, Card, Badge, Tab, Input,
>   Table, Chart, Search, Sidebar, Watchlist).
> - `docs/ui-system/brand/README.md` — locked color palette, typography, and brand rules.
> - `frontend/styles/tokens.json` → `frontend/src/styles/tokens.css` — single source of
>   truth for all CSS variables and Tailwind token mappings.
>
> **Never use magic numbers.** Always use CSS variables (`--bg`, `--surface`, `--text`,
> `--border`, `--royal`, etc.) or the Tailwind token classes (`bg`, `surface`, `ink`,
> `line`, `royal`, `emerald`, `amber`, `red`).
>
> **Never hardcode font stacks.** Use `var(--dr-font-sans)` and `var(--dr-font-mono)`.
>
> **Always use `.mono` with `font-feature-settings:'tnum'`** for all ₹ amounts,
> percentages, and numeric data values.

---

## 4. Architecture

### Route

```
/signal                   → Signal page, "Today" tab active by default
/signal?tab=rules         → Rules & Fund tab
/signal?tab=reflect       → Reflect tab
```

Tab state is persisted in the URL query param `tab` so tabs are shareable/bookmarkable.
The page is a single client component with internal tab switching — no sub-routes.

### Access

- All logged-in users (`RequireAuth`).
- No tier gate at launch — Signal is available to all users.
- `page.tsx` is a **server component** that fetches `hasCAS: boolean` (checks whether the
  user has any portfolio in the DB) and passes it as a prop to the client `<SignalPage>`
  component. The client component never fetches auth-gated existence checks directly.
  When `hasCAS === false`, a non-blocking CAS upload prompt banner is shown at the top of
  the Today tab.

### Navigation

Signal is added to `AppShell.tsx` WORKSPACE nav array as the 5th item (after Market Mood):

```typescript
{ label: 'Signal', href: '/signal', icon: SignalIcon }
```

---

## 5. Tab Specifications

### Tab 1 — Today

**Purpose:** Answer "do my rules say anything today?" in under 10 seconds.

**Sections (top to bottom):**

#### 5.1.1 CAS Prompt Banner (conditional)

Shown only when `hasCAS === false`.

```
Component: inline banner, not a modal
Classes:   cas-banner (blue-soft bg + 18% royal border)
Content:   icon | "Link your portfolio for deeper context" | [Upload CAS] | [Later]
Dismiss:   "Later" hides banner for the session (localStorage key: `signal_cas_dismissed`)
```

#### 5.1.2 Signal Hero Card

Uses the same card structure (`rec` / `rec-top` / `rec-body` / `rec-foot` CSS classes) as
the RecommendationCard pattern in `docs/ui-system/components/RecommendationCard.md`, but is
a **distinct component** (`SignalHero.tsx`) — it does not render fund scores, targets, or
advisory labels. The shared classes give visual consistency; the content is entirely different.

**States:**

| State | Ring colour | Border accent | Label | Confidence badge |
|---|---|---|---|---|
| Triggered | `--positive` | `--positive` | "Rules triggered" | `badge-pos` HIGH |
| Watch | `--warn` | `--warn` | "Watch — Mixed conditions" | `badge-warn` MEDIUM |
| No signal | `--text-faint` | `--border-strong` | "No action — Conditions not met" | `badge-neutral` HIGH |

Ring is a 64×64 SVG score ring (same pattern as `docs/ui-system/html/` ScoreRing component).
Fill fraction: Triggered = 100%, Watch = 50%, No signal = 10%.

Footer always includes:
```
📋 NOT FINANCIAL ADVICE — Based on your own configured thresholds
```

#### 5.1.3 Market Signal Cards (3-column grid)

One card per signal parameter. Each card uses `.card.card-pad` (14px radius, surface bg).

**Nifty 50 card:**
- Value: current Nifty index (`.t22.mono`)
- Change: pts + % (`.t11.mono.neg` or `.pos`)
- Progress bar: score/4 as fill width, colour matches state
- Score badge + weight pill (`.badge-neutral`)
- Divider then: short trend description + user threshold callout

**India VIX card:**
- Same structure; border tinted `rgba(245,166,35,0.3)` when in "close" zone
- Inline threshold callout box: `warn-soft` bg, `2px solid --warn` left border

**Market Breadth card:**
- Advances / Declines as side-by-side `.t18.mono.pos` / `.neg`
- A/D ratio as `.t11.mono`
- Same score bar + weight

**Score mapping:**

| Score | Nifty | VIX | Breadth |
|---|---|---|---|
| 0 | Strong bullish | VIX < 15 | A/D > 1.5 |
| 1 | Bullish | 15–17 | A/D 1.2–1.5 |
| 2 | Neutral | 17–19 | A/D 0.8–1.2 |
| 3 | Bearish | 19–22 | A/D 0.5–0.8 |
| 4 | Strong correction | VIX > 22 | A/D < 0.5 |

**Weighted overall score** (not displayed in DOM — used only for state logic):
`score = nifty_score × 0.20 + vix_score × 0.40 + breadth_score × 0.40`

Thresholds → state:
- score ≥ 3.0: Triggered
- score ≥ 2.0: Watch
- score < 2.0: No signal

#### 5.1.4 Portfolio Context Card (conditional on hasCAS)

When `hasCAS === false`: show `.empty` state with Upload CAS CTA.
When `hasCAS === true`:

- **SIP progress bar:** monthly target vs completed, gradient fill (`--royal → --info`).
- **Stats table:** `.dt` pattern — portfolio value, overall gain (`badge-pos`), drawdown from peak, funds in correction.
- **Impact note box:** `info-box` (blue-soft bg, 2px royal left border) — which funds changed label today.
- **Deployment Ladder:** 5-step visual bar showing S1–S5 percentages. Nearest triggered step highlighted with `near` class (`warn-soft` bg, `warn` border).

#### 5.1.5 Learning Content Card

Contextual: articles are filtered to match today's dominant signal.
- VIX elevated → show VIX explainer first.
- Breadth weak → show breadth explainer first.
- No signal → show SIP discipline content.

Each item: 32×32 icon box (colour matches signal type) + title + description + optional `badge-neutral` time-to-read chip.
Link: `/learn/concepts/[slug]` or `/learn/tax/[slug]`.

---

### Tab 2 — Rules & Fund

**Purpose:** Configure signal thresholds + manage dip fund capital.

#### 5.2.1 Signal Thresholds Card

Three threshold rows (Nifty / VIX / Breadth), each with:
- `.label` (mono, uppercase): parameter name + description
- `.t22.mono` current value (colour: `--warn` or `--negative` or `--info`)
- HTML `<input type="range">` using `.slider` class from ui-system
- Range labels (min/max hints) + `.badge.badge-neutral` showing signal weight
- Row separator: `border-bottom: 1px solid var(--border)`

Default values stored in user settings table `signal_rules` (see §8).
Weights are fixed (20/40/40) and not user-editable at launch.

Footer row: `[Save Rules]` (`.btn.btn-accent`) · `[Reset to defaults]` (`.btn.btn-ghost`) · Daily alerts toggle (`.toggle.on`)

Daily alerts = in-app toast at 09:15 IST on trading days when `signal_state === 'triggered'`.
No push at launch; wired to `settings/notifications` toggle in Phase 3.

#### 5.2.2 Dip Fund Capital Card

**KPI pair** (`.kpi-card` grid-2):
- Available (`.pos-soft` bg): current dip fund balance in `.t22.mono.pos`
- Monthly addition: fixed amount in `.t22.mono`

**Deployment Ladder** — 5 rows:
- Label (`Signal N`) + progress bar fill (width = pct %) + pct value (`.t13.mono`) + ₹ amount (`.t11.mono.muted`)
- ₹ amount = `available_balance × pct / 100`
- Footer note: "Total max 100% across 5 deepening signals."

Buttons: `[Edit amounts]` · `[Add cash manually]` — both `.btn.btn-ghost.btn-sm`

#### 5.2.3 How Signal Works Explainer (right column)

`info-box` card (blue-soft bg, `var(--dr-r-xl)` radius).
Explains threshold check logic in plain English.
Never references specific fund or stock names.

#### 5.2.4 Deployment History Table

`.card` with overflow hidden, `.dt` table inside:
Columns: Date (`.mono.muted`) · Action · Amount (`.mono.right`) · Signal (badge).
Badge colours: Triggered = `badge-pos`, Watch = `badge-warn`, No signal = `badge-neutral`.

---

### Tab 3 — Reflect

**Purpose:** Journal past decisions and see behaviour analytics over time.

#### 5.3.1 Behaviour Score KPIs (3-column)

Three `.kpi-card` cards, each with a 52×52 SVG score ring + numeric score + label.

| Score | Ring colour | Calculation |
|---|---|---|
| Investor Score | `--positive` | Composite: 40% discipline + 40% patience + 20% trust engine. If trust engine has no data yet (< 90 days), redistribute: 50% discipline + 50% patience. |
| Discipline Score | `--info` | `days_on_rules / total_days × 100`. Starts at 100 on day 1. |
| Patience Score | `--warn` | `fomo_avoided / (fomo_avoided + premature_deployments) × 100`. If both are 0 (no events logged), display 100 — perfect patience by default. |

Scores are user-behaviour metrics (0–100 integer). No SEBI-regulated content.
Ring dash math: `circumference = 2π × r`. Fill: `stroke-dashoffset = circumference × (1 - score/100)`.

#### 5.3.2 Investment Journal

Header row: `[+ Log today]` (`.btn.btn-accent.btn-sm`) + section label.

Journal entry (`.j-entry`) — 3 states via class:
- `.deployed` → `border-left: 3px solid var(--positive)`
- `.watched` → `border-left: 3px solid var(--warn)`
- `.skipped` → `border-left: 3px solid var(--text-faint)`

Each entry contains:
- Date `.t11.mono.muted` + decision badge + emotion chip (`.chip`)
- Note text `.t12.sec`
- Market snapshot row: Nifty / VIX / A/D + signal badge

"+ Add a past entry" button: `1px dashed var(--border-strong)`, full width.

**Log today modal** fields:
- Date (auto-filled, editable)
- Decision: radio — Deployed / Watched / Skipped
- Amount deployed (shown only if Deployed)
- Emotion: multi-select chips (Fearful / Calm / Excited / FOMO / Disciplined)
- Notes: textarea
- Market snapshot: auto-filled from API, user can override

#### 5.3.3 Behaviour Summary

`.card.card-pad` with `.dt` table:
- Days following rules / FOMO avoided / Premature deployments avoided / Cash preserved / SIP streak
- Numeric values in `.t16.w-700.mono`, coloured by semantic meaning

#### 5.3.4 Trust Engine

`.card.card-pad` with `.dt` table.
Shows past signals and market outcome 3 months later.
Columns: Signal date + state · Your action (badge) · Market outcome (`.mono.pos/.neg`)

**Display rules:**
- Only show rows where 3 months have elapsed since the signal date.
- Cap at 10 most recent rows.
- Always show disclaimer block below table.

Disclaimer block: `pos-soft` bg, `rgba(0,179,134,0.25)` border:
```
"3 of N triggered signals beat waiting"
"Past accuracy does not predict future outcomes. Educational context only."
```

#### 5.3.5 Achievements

`.card.card-pad` with 2-column grid of `.achievement` cards.

| Achievement | Condition | Colour |
|---|---|---|
| Disciplined Investor | 90+ days on rules | `pos` / emerald |
| Bear Market Hunter | Deployed at VIX > 20 | `info` / cyan |
| Patience Master | Avoided 3+ FOMO traps | `warn` / amber |
| Crash Collector | Deployed at Nifty −15% or lower | locked until earned |
| Long-Term Legend | 5-year SIP streak | locked until earned |
| Market Survivor | Any deployment during VIX > 25 | locked until earned |

Locked achievements: `.achievement.locked` (opacity 0.4, 🔒 icon).
Earned: `.achievement.earned` (`pos-soft` bg, `rgba(0,179,134,0.3)` border).

---

## 6. Theme Support

The page supports **light and dark themes** via `data-theme` on `<html>`.

Theme switching is handled by the existing DhanRadar theme mechanism.
Signal page uses only CSS variables — never hardcoded hex colours — so it inherits
theme switches automatically.

**Light mode tokens used:**
```
--bg: #F7F6F2   --surface: #FFFFFF   --surface-2: #F1EFE9
--border: #E4E1D9   --text: #0B0F1A   --positive: #00B386
--negative: #E5484D   (all others same as dark)
```

**Dark mode tokens:**
```
--bg: #07090F   --surface: #0E121E   --surface-2: #141928
--border: rgba(255,255,255,0.06)   --text: #ECEEF5   --positive: #1FD79A
--negative: #FF6166
```

---

## 7. Data Sources & APIs

### Market Data (read-only, fetched on page load + polling every 60s during market hours)

| Signal | Source | Endpoint / Method |
|---|---|---|
| Nifty 50 | NSE / existing `useIndices` hook | `/api/v1/market/indices` |
| India VIX | NSE | `/api/v1/market/vix` (new endpoint) |
| Market Breadth (A/D) | NSE | `/api/v1/market/breadth` (new endpoint) |

Market hours: 09:15–15:30 IST Monday–Friday. Outside hours: use last available values, show "Market closed" label.

### User Data (authenticated, per-user)

| Data | Table | Notes |
|---|---|---|
| Signal thresholds | `signal_rules` | Per-user, JSONB; defaults seeded on first visit |
| Dip fund balance | `signal_dip_fund` | Balance + monthly addition + last updated |
| Deployment history | `signal_deployments` | Date, amount, signal state, market snapshot |
| Journal entries | `signal_journal` | Date, decision, amount, emotion, notes, market snapshot |
| Behaviour scores | Computed from `signal_journal` + `signal_deployments` | Not stored; derived on load |
| Trust engine rows | Computed from `signal_deployments` + `signal_journal` + market history | Only rows ≥ 90 days old |

### Portfolio Data (from existing MF module — hasCAS path)

Reuses existing hooks:

- `usePortfolioSummary(portfolioId)` — value, gain, drawdown. Uses the user's **most
  recently updated portfolio** (`ORDER BY updated_at DESC LIMIT 1`). If the user has
  multiple portfolios, Signal shows the primary one; multi-portfolio selection is out of
  scope at launch.
- MF report label data — which funds changed label today (latest report for the same portfolio)

---

## 8. Backend — New API Endpoints Required

All under `/api/v1/signal/`. Auth: `RequireAuth` (JWT HttpOnly cookie). No tier gate at launch.

```
GET  /api/v1/signal/today
     → { nifty, vix, breadth, signal_state, confidence, rules_checked }

GET  /api/v1/signal/rules
     → { nifty_threshold, vix_threshold, breadth_threshold, deploy_ladder[], alerts_on }

PUT  /api/v1/signal/rules
     body: { nifty_threshold, vix_threshold, breadth_threshold, deploy_ladder[], alerts_on }

GET  /api/v1/signal/dip-fund
     → { balance, monthly_addition, last_updated, deployments[] }

POST /api/v1/signal/dip-fund/add
     body: { amount }  → updates balance

GET  /api/v1/signal/journal
     → { entries[] }

POST /api/v1/signal/journal
     body: { date, decision, amount, emotion[], notes, market_snapshot }

GET  /api/v1/signal/analytics
     → { investor_score, discipline_score, patience_score, behaviour_summary, trust_engine[] }

GET  /api/v1/market/vix       (new)
GET  /api/v1/market/breadth   (new)
```

All responses follow RFC 7807 + `request_id`. Errors use existing error envelope.

---

## 9. Frontend Component Map

```
app/(app)/signal/
  page.tsx                    ← Signal page (client component, tab state)
  loading.tsx                 ← Skeleton loader

components/signal/
  SignalHero.tsx              ← Rec card pattern: ring + state + reason + footer
  MarketSignalCard.tsx        ← Nifty / VIX / Breadth card (accepts config prop)
  PortfolioContext.tsx        ← SIP progress + stats + impact note + ladder
  LearningContent.tsx         ← Contextual learn links
  RuleThresholdForm.tsx       ← Sliders + save/reset
  DipFundCard.tsx             ← KPIs + ladder bars + add cash
  DeploymentHistory.tsx       ← .dt table
  JournalEntry.tsx            ← .j-entry card
  LogTodayModal.tsx           ← Decision log form
  BehaviourKPIs.tsx           ← 3 score rings
  BehaviourSummary.tsx        ← Stats .dt table
  TrustEngine.tsx             ← History table + disclaimer
  Achievements.tsx            ← Achievement grid

features/signal/
  api.ts                      ← TanStack Query hooks (useSignalToday, useSignalRules, etc.)
  types.ts                    ← TypeScript interfaces
```

**Component guidelines:**
- Each component is a single-purpose, independently testable unit.
- Props interfaces defined in `types.ts` — no inline prop types in JSX files.
- All data fetching via TanStack Query hooks in `features/signal/api.ts`.
- No direct `fetch` calls inside components.
- All monetary values formatted with `Intl.NumberFormat('en-IN', { style:'currency', currency:'INR' })`.

---

## 10. Notifications

Push/email notifications (MVP: in-app only; push later):

| Event | Trigger | Message |
|---|---|---|
| Signal triggered | Score ≥ 3.0 on market open | "Your rules are triggered today — VIX 22.1, Nifty −9.2%" |
| VIX alert | VIX crosses user threshold | "VIX just crossed 19.0 — Signal check: Watch" |
| Breadth collapse | A/D < 0.5 | "Market breadth in panic zone — check Signal" |
| Morning market open | 09:15 IST | "Markets open. Today's signal: [state]" |
| SIP reminder | 5 days before SIP date | "SIP due in 5 days — ₹22,000 pending" |

Notifications shown as toast (`.toast` pattern from ui-system) in-app.
User can toggle per-type in Settings.

---

## 11. Mobile Considerations

Signal is responsive. Below `md` breakpoint (768px):

- Sidebar collapses to bottom tab bar (existing AppShell behaviour).
- `grid-3` → single column stack.
- `grid-21` → single column stack (portfolio context above learning).
- Tab bar: 3 tabs fit comfortably (Today / Rules & Fund / Reflect).
- Deployment ladder: horizontal scroll container if viewport < 360px.
- Journal entries: full width, comfortable touch targets (min 44px height).
- Score rings: reduce to 44×44 on smallest screens.

---

## 12. Empty States

| Situation | Empty state |
|---|---|
| No journal entries | `.empty` box: "No decisions logged yet. + Log today's decision" |
| No deployment history | `.empty` box: "No deployments yet. Your dip fund is ready when the signal triggers." |
| hasCAS === false (portfolio context) | `.empty` box: "Upload your CAS to see portfolio context here." + Upload CAS button |
| Trust engine < 1 row | Hide section entirely; show placeholder: "Trust engine needs at least one signal 3+ months ago." |
| Market closed | Signal Hero shows last values with "Market closed · Last updated HH:MM" badge |

---

## 13. Phased Rollout

### Phase 1 — Core (ship first)

- Today tab: market signals + signal hero + CAS prompt
- Rules & Fund tab: threshold config + dip fund balance + deployment history
- Sidebar nav entry

### Phase 2 — Journal + Analytics

- Reflect tab: journal log + behaviour summary
- Trust Engine (requires 90 days of history — can show empty state at launch)

### Phase 3 — Intelligence

- Contextual learning content (API-driven, not hardcoded)
- Push notifications
- Achievements unlock logic
- Behaviour score computation

### Phase 4 — Automation

- Auto-fetch market data on schedule (existing Celery batch infra)
- Auto-log "No action" entries on non-deployment days
- SIP reminder notifications
- Trust engine historical backfill

---

## 14. Open Questions

1. **VIX and Breadth data source** — Does DhanRadar have an existing NSE data pipeline for
   VIX and advance/decline data, or does this require a new ingestion job?
2. **Notification delivery** — In-app toast is MVP; which push provider for Phase 3?
3. **Default thresholds** — Are the defaults (VIX 19, Nifty −8%, A/D 0.80) validated against
   historical data, or are they illustrative?
4. **Dip fund seeding** — Should the first dip-fund balance be user-entered on first visit,
   or default to ₹0?
5. **Achievements timing** — Do achievements unlock in real-time or on next page load?

---

## 15. UI Consistency Checklist (for every PR touching Signal or any other DhanRadar page)

Before raising a PR for any UI change:

- [ ] Checked `docs/ui-system/html/dhanradar-design-system.html` for component markup
- [ ] Checked `docs/ui-system/components/` for component spec
- [ ] All colours use CSS variables — no hardcoded hex
- [ ] All ₹/% values use `.mono` class (`font-family: var(--dr-font-mono); font-feature-settings:'tnum'`)
- [ ] Labels use `.t10/.t11.upper.muted.mono` pattern
- [ ] Cards use `.card.card-pad` (`border-radius: 14px`, `border: 1px solid var(--border)`)
- [ ] Tabs use `.tabs` / `.tab` / `.tab.active` with `border-bottom-color: var(--text)` on active
- [ ] Badges use `.badge.badge-pos/.badge-neg/.badge-warn/.badge-neutral`
- [ ] Buttons use `.btn.btn-primary/.btn-accent/.btn-ghost/.btn-outline`
- [ ] Light and dark mode tested (toggle `data-theme` on `<html>`)
- [ ] No advisory verbs in copy — only Triggered / Watch / No signal
- [ ] `NOT FINANCIAL ADVICE` disclaimer present on every signal surface
- [ ] `tsc` passes with 0 errors
- [ ] `ruff` + `mypy` pass on backend changes
