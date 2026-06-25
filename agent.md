# DhanRadar — UI/UX Development Instructions (agent.md)

## Canonical design source (read this first)

The single source of truth for DhanRadar UI is the **live `frontend/` token files** (Geist
Sans/Mono + Instrument Serif, warm "locked" palette), emitted by the
`frontend/scripts/gen-tokens.mjs` pipeline: `frontend/styles/tokens.json` (hand-maintained
master) → `frontend/src/styles/tokens.css` + `frontend/tailwind.config.js` /
`frontend/tailwind.tokens.cjs` (Tailwind color keys `royal`, `ink-secondary`, etc.). The decision
is recorded in **`docs/project-state/CANONICAL_DESIGN_SYSTEM_ALIGNMENT.md`** (D1). The built,
compliant components live in `frontend/src/components/` — reuse those; never copy from a spec.

**REMOVED (2026-06-06) — gone from the repo, never resurrect:** the Manrope/cool token sets
`docs/ui-system/design-system/` + `docs/ui-system/tokens/`, the pre-compliance component source
`docs/ui-system/reference-impl/`, and the stale Geist token mirror under `docs/ui-system/brand/`.
**Reference only (retokenize to Geist/warm + relabel advisory copy before building):**
`docs/ui-system/components/*`, `docs/ui-system/screens/*`, `docs/ui-system/figma/*`,
`docs/ui-system/html/*`, and the brand guide `docs/ui-system/brand/` (README + `mockups/`). The
full map is in `docs/ui-system/README.md`.

## Design authority vs the SEBI boundary (hard)

The design package is a **reference system**, not a complete spec, and is a **living** system —
you may create missing screens/components and improve patterns. **UI never overrides a
non-negotiable.** The rules are defined authoritatively in project `CLAUDE.md`
(§Non-negotiables) — do not restate them here; the UI bindings that follow are:

- **#1** → no advisory copy/labels; `RecommendationCard` + any label UI use
  `in_form/on_track/off_track/out_of_form` + confidence **band**.
- **#2** → `ScoreRing` + any score UI render the confidence band, never a raw numeric score; the
  numeric score / factor-weights / fair-value never enter the DOM.
- **#9** → every score/label/AI surface renders the disclosure bundle + `NOT_ADVICE`.

Where the design package shows advisory framing or a numeric score, **relabel/regate first**, then
build.

## When a matching design exists

Reuse it; follow the established (Geist/warm) design language; reuse tokens and components;
maintain visual consistency.

## When no design exists

Design a new solution in the existing branding + tokens + component patterns. Create reusable
components; document them. **Do not block implementation because a design is missing — create the
missing (compliant) design and continue.** A user must not be able to tell which screens came from
the original package and which were created during implementation.

## Engineering priority (when implementation conflicts with the design package)

Prioritise: functional correctness · accessibility · performance · mobile responsiveness ·
security · scalability · design consistency. **Document deviations** in the feature doc.

## New components

Use existing tokens, spacing, typography; support dark mode, mobile, accessibility; be reusable.
Add to `frontend/src/components/` (the adopted `src/` feature-slice structure) and document them in
the module feature doc / component spec. No magic numbers (token-only).

## Always render — never suppress a component for missing data (founder rule 2026-06-25, binding)

No UI **section, card, table, filter, or button** may be deleted, hidden, conditionally removed,
or `return null`-ed just because its backend data is empty or missing. The component **stays
mounted** and renders a clear **"no data" state** (reuse `@/components/ui/EmptyState`, or an inline
empty/disabled treatment for buttons/filters). The UI is built ahead of its backends, so a visible
"no data yet" preserves the full intended layout instead of making a page look incomplete.

- **Forbidden:** `{data && <SomeSection/>}` that removes the section, `if (rows.length === 0) return
  null` in a section/table, a `.map()` with no empty fallback, swapping a section out on data
  presence.
- **Allowed any time (cosmetic exception):** small alignment, nav fixes, breadcrumbs, color,
  typography, and font may be adjusted freely while the backend + functionality are still being
  built. The rule freezes *removal*, not *refinement*.
- **Compliance still wins:** no numeric-in-DOM (#2) and no advisory copy, even inside empty states.
- **Enforced** by `scripts/ci_guards.py` (#9, runs in the `guards` CI job). Pre-existing cases are
  grandfathered in `scripts/no_suppress_baseline.txt`; a genuinely-conditional non-data case uses an
  inline `// no-suppress-ok: <reason>` comment. Any NEW suppression fails the build.

## New pages

Reuse existing layouts, navigation, cards/widgets; maintain visual hierarchy. Build production-
quality pages (no placeholder-only screens); prefer complete working experiences.

## Governance gate for UI work

UI work is at least **Tier A** (UI Review; +Compliance Review if it surfaces a score/label/AI
output). Whether those reviews run **inline or batch to the end-of-phase audit** is set by
`CLAUDE.md` (review cadence) + `docs/project-state/AI_GOVERNANCE_MODEL.md` — follow those; don't
restate the tier mechanics here. New tokens are added under brand naming only. Per-change review
output lives in `docs/project-state/reviews/<change-id>.md`.

## Definition of done (per UI feature)

Four states (loading/empty/error/success) · a11y pass (focus rings, chart text-alternatives,
axe + Lighthouse budgets) · analytics events fired (typed `track()`) · error-catalog mapping ·
disclosures where applicable · within perf/bundle budget · token-compliant (no magic numbers).
