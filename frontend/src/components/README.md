# DhanRadar Component Catalog

The **canonical, shipping** UI components. This is the single index of what exists in
`frontend/src/components/` and how to use it. **Reuse these before inventing anything new.** Build
rules live in `../../../agent.md`; design reference (specs, screens, mockups) lives in
`../../../docs/ui-system/` and must be retokenized to Geist/warm before use.

## Compliance — non-negotiable (project `CLAUDE.md`)

These are enforced by `scripts/ci_guards.py` on shipped code:

- **No numeric score / factor weights / fair-value in the DOM (#2).** Score surfaces show a
  **label + confidence band**, never a 0–100 number.
- **Educational labels only (#1).** `in_form / on_track / off_track / out_of_form /
  insufficient_data`. Advisory verbs (`strong_buy/buy/hold/caution/avoid`) are rejected.
- **Disclosure on every score/label/AI surface (#9)** — the standing line lives once in layout
  chrome (`<Disclaimer>` in the AppShell/auth/public-page footer); the contextual, version-tied
  disclosure (`disclosure` + `not_advice`) renders next to the content via `<DisclosureBundle>`.
- **Geist/warm tokens only; no magic numbers** (token classes such as `royal`, `surface`, `line`,
  `ink-secondary`; never `blue`/`ink-2`).

## Primitives — `components/ui/`

| Component | Purpose | Key props |
|---|---|---|
| `Button` | Polymorphic button; `asChild` (Radix Slot) renders styled links without nested `<a>`. | `variant?: 'primary'\|'secondary'\|'ghost'\|'outline'\|'danger'` (def `primary`), `size?: 'sm'\|'md'\|'lg'` (def `md`), `asChild?` |
| `Card` | Surface container (`bg-surface`/`border-line`). Exports `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardBody`, `CardFooter`. | `className`, `children` |
| `Input` + `Field` | Token-styled text input with `aria-invalid` danger state; `Field` wires `htmlFor`/`id`/`aria-describedby`. | `Input`: native input attrs. `Field`: `id`, `label` (req), `error?`, `hint?` |
| `Disclaimer` | Mandatory NOT_ADVICE educational note (#9). `<p role="note">` with the fixed disclaimer text. | `className?` |
| `EmptyState` | Centred empty slot (icon/title/description/action). | `title` (req), `icon?`, `description?`, `action?` |
| `ErrorCard` | Bordered error surface with optional retry (`outline/sm` Button). | `title?` (def "Something went wrong"), `message?`, `onRetry?` |
| `LabelChip` | Educational label as a coloured pill, optional confidence-band suffix. | `label: Label` (req), `confidenceBand?: ConfidenceBand` |
| `ProgressBar` | `role="progressbar"` bar for upload/processing. `value` is UI progress, not a score; not rendered as text. | `value: number` (0–100, req) |
| `Skeleton` | Pulse loading placeholder; caller sizes via `className`. | native div attrs |
| `AppShell` | `'use client'` authenticated layout: 56px sidebar (brand + nav) + topbar (`userSlot`) + scrollable `<main>`. Nav: Dashboard, Upload CAS, Market Mood, Notifications; footer "Educational use only". | `children` (req), `userSlot?` |

## Charts — `components/charts/`

| Component | Purpose | Key props |
|---|---|---|
| `ScoreRing` | **Compliance-critical.** SVG ring showing a **label + confidence band** — there is **no `score` prop** and no 0–100 value anywhere. Ring fill is a visual-only band fraction. | `label: Label` (req), `confidenceBand: ConfidenceBand` (req), `ariaLabel?` |
| `AllocationDonut` | SVG donut of portfolio category allocation; legend renders `{pct}%`. | `data: { category: string; pct: number }[]` (req), `size?` (def 180), `strokeWidth?` (def 26) |

> **AllocationDonut numeric note:** the `%` it renders is the user's own **portfolio composition**
> share (e.g. "Equity 65%"), not a score / factor-weight / fair-value, so it does not fall under
> non-negotiable #2. Keep it that way — never feed a score or rating into this component.

## Feature components

| Component | Path | Purpose | Key props |
|---|---|---|---|
| `FileDrop` | `components/mf/` | `'use client'` accessible drag-drop / click file picker for CAS PDF upload (keyboard + `aria-disabled`). | `onFile: (f: File) => void` (req), `accept?` (def `.pdf`), `disabled?` |
| `MoodGauge` | `components/mood/` | **Compliance-critical.** Semicircular SVG gauge for Mood Compass: renders a **regime word + confidence band**, no numeric. Needle from a discrete ordinal (0–4), not a score. Symmetric colour (both extremes → red) so greed ≠ "buy". | `regime: Regime` (req), `confidenceBand: string` (req) |

## Shared types

`Label` and `ConfidenceBand` are exported from `components/charts/ScoreRing` and reused by
`LabelChip` and `MoodGauge` — import them from there, do not redefine.

- `Label` = `'in_form' | 'on_track' | 'off_track' | 'out_of_form' | 'insufficient_data'`
- `ConfidenceBand` = `'high' | 'medium' | 'low'`
- `Regime` = `'extreme_fear' | 'fear' | 'neutral' | 'greed' | 'extreme_greed' | 'insufficient_data'`

## Adding a component

Use existing tokens/spacing/typography; support dark mode, mobile, and a11y; be reusable; no magic
numbers. Add it here and document it in this catalog + the module feature doc. New tokens go under
brand naming only and through UI Review (see `../../../agent.md`).
