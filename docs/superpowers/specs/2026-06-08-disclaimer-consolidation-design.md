# Disclaimer Consolidation — Design Spec

Date: 2026-06-08
Status: Approved (design)
Area: `frontend/` — compliance disclosure surfaces (non-negotiable #9)

## Problem

The SEBI "educational / not investment advice" message appears across the app in
inconsistent locations and forms: a centered footer on the dashboard, a bordered
card on the report, inside the consent modal, the bottom of the auth card, plus
scattered half-sentence "educational research only" subtitle fragments on most
pages. It reads as "the same warning sprinkled everywhere at random," which is
both a UX-noise problem and dilutes the disclosure's weight.

## Principle (the fix)

Separate two things that are currently conflated, and give each exactly one home:

1. **Standing disclaimer** — the full SEBI line rendered by the shared
   `<Disclaimer/>` component. Home = **layout chrome only, as a bottom-of-page
   footer**. Never a mid-page card, never an inline subtitle.
2. **Contextual compliance disclosure** — backend `disclosure` + `not_advice`
   (tied to `disclaimer_version`). Home = **adjacent to the actual
   score/label/AI output**, via one shared `<DisclosureBundle/>` component.
   Required by non-negotiable #9.

There is no single global layout — there are three shells, so "one spot" means
one spot per shell.

## Changes

### New component
- `frontend/src/components/ui/DisclosureBundle.tsx` — renders backend
  `disclosure` (optional) + `not_advice` captions as a `role="note"` block.
  Props: `{ disclosure?: string; notAdvice: string; className?: string }`.
  Shared by the report and mood pages.

### Standing disclaimer → footer-only
- `components/ui/AppShell.tsx` — add `<footer><Disclaimer/></footer>` at the end
  of `<main>` (after `{children}`). Covers all 6 `(app)` pages automatically.
  Keep the sidebar "Educational use only" chip and "Research Analytics" topbar
  label (consistent persistent chrome, not part of the scatter).
- Remove the now-redundant manual `<Disclaimer/>` from:
  - `app/(app)/dashboard/page.tsx` (L271)
  - `app/(app)/mf/upload/page.tsx` (L136)
  - `app/(app)/settings/privacy/page.tsx` (L177)
  - `app/(app)/mf/report/[jobId]/page.tsx` (L236–238, the bordered card)
- No change to `(auth)/layout.tsx` (already one footer) or the standalone public
  `home` / `mood` footers (already one footer each, page-bottom).
- `features/consent/ConsentModal.tsx` keeps its `<Disclaimer/>` — a modal overlay
  hides the page footer, so the consent surface carries its own.

### Close the report #9 gap
The report fetches `disclosure`/`not_advice`/`disclaimer_version` but never
renders them (obs 5918). Since its standing card is being removed:
- `features/mf/types.ts` — add `disclosure: string` and `not_advice: string` to
  `MfReport`.
- `features/mf/api.ts::mapBackendReport` — pass `r.disclosure` / `r.not_advice`
  through.
- `app/(app)/mf/report/[jobId]/page.tsx` — render `<DisclosureBundle/>` directly
  under the Holdings card (adjacent to the labels), using the mapped fields.

### Mood
- `app/mood/page.tsx` — replace the two hand-written `disclosure`/`not_advice`
  `<p>` tags (L224–225) with `<DisclosureBundle disclosure={data.disclosure}
  notAdvice={data.not_advice} />`. Keep the footer `<Disclaimer/>`.

### Remove redundant subtitle fragments
- `dashboard` L240: `Indian market overview · educational research only` →
  `Indian market overview`.
- `mood` L122: drop the trailing `Not investment advice.` sentence (keep
  "An educational read of market sentiment, updated twice daily.").
- `report` L257: `Educational analysis · not investment advice` → drop the
  advisory tail (descriptive subtitle only).
- `home` L13–14: remove the `Educational research only — never investment
  advice.` line (footer `<Disclaimer/>` carries it).

### Deliberately NOT touched
- `onboarding` L29 — "This profile is for display purposes only and is not
  investment advice." is a distinct contextual claim (risk-profile ≠ advice,
  non-negotiable #3), not a duplicate of the standing line. Onboarding gains the
  AppShell footer automatically (it had none before — a consistency + #9 win).

## Acceptance

- Every `(app)` page renders the standing disclaimer exactly once, as the
  AppShell `<main>` footer; no page in the group renders `<Disclaimer/>` itself.
- The report renders `<DisclosureBundle/>` adjacent to the holdings labels with
  the backend-supplied `disclosure` + `not_advice`.
- Mood renders the same `<DisclosureBundle/>` plus the footer `<Disclaimer/>`.
- No advisory-verb regressions (anti-pattern grep clean).
- `tsc` clean. No existing test asserts `<Disclaimer/>` placement (verified —
  none reference it), so no test breakage expected; add none unless a gate needs.

## Review classification

Tier A (UI) + Compliance cross-tier (touches the #9 disclosure surface).
Compliance reasoning is done inline by the orchestrator (Opus); UI review batched
to the phase audit per the project review cadence. Deterministic gates (tsc,
anti-pattern grep) run per commit.
