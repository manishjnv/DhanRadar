# DhanRadar — UI/UX Development Instructions (agent.md)

## Canonical design source (read this first)

The single source of truth for DhanRadar UI is **`docs/brand/` (Geist Sans/Mono +
Instrument Serif, warm "locked" palette)** as reconciled in
**`docs/project-state/CANONICAL_DESIGN_SYSTEM_ALIGNMENT.md`**, materialised in the repo token
files: `frontend/tailwind.config.js`, `frontend/app/tokens.css`, `frontend/styles/tokens.json`
(Tailwind color keys `royal`, `ink-secondary`, etc.).

**RETIRED — do NOT build against these:** `docs/ui-system/design-system/` and
`docs/ui-system/tokens/` (Manrope/Inter + cool palette, keys `blue`/`ink-2`). They are a competing
language and are superseded. `docs/ui-system/reference-impl/*`, `docs/ui-system/figma/*`, and the
`/screens` specs are **visual reference only** and must be **retokenized to brand (Geist/warm)**
before they compile or ship. `docs/ui-system/html/*` mockups are reference-only.

## Design authority vs the SEBI boundary (hard)

The design package is a **reference system**, not a complete spec, and is a **living** system —
you may create missing screens/components and improve patterns. **But UI never overrides a
non-negotiable** (see project `CLAUDE.md`):

- No advisory copy or advisory labels anywhere. `RecommendationCard` and any label UI use
  `in_form/on_track/off_track/out_of_form` + confidence **band**.
- `ScoreRing` and any score UI render the **confidence band, not a raw numeric score** on ungated
  views — numeric score / factor-weights / fair-value never appear in the DOM.
- Every surface showing a score/label/AI output renders the disclosure bundle + `NOT_ADVICE`.

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

## New pages

Reuse existing layouts, navigation, cards/widgets; maintain visual hierarchy. Build production-
quality pages (no placeholder-only screens); prefer complete working experiences.

## Governance gate for UI work (`docs/project-state/AI_GOVERNANCE_MODEL.md`)

Any user-facing screen or shared component is at least **Tier A**: it requires a **UI Review**
(branding · design system · accessibility · mobile · token compliance). If it surfaces a
score/label/AI output, a **Compliance Review** is also required. New tokens are added under brand
naming only and go through UI Review. All review output for the change lives in the single file
`docs/project-state/reviews/<change-id>.md`.

## Definition of done (per UI feature)

Four states (loading/empty/error/success) · a11y pass (focus rings, chart text-alternatives,
axe + Lighthouse budgets) · analytics events fired (typed `track()`) · error-catalog mapping ·
disclosures where applicable · within perf/bundle budget · token-compliant (no magic numbers).
