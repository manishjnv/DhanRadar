# DhanRadar — UI System (master design)

> **START HERE.** This folder is the **master UI design and the FIRST source of truth** for every UI
> change and every new page (founder rule 2026-06-19). The `frontend/` pages are the **older build** —
> bring them UP TO this master, don't treat them as the design truth. Build the *design* from here;
> implement it through the `frontend/` token pipeline + components (the mechanism).

## Use this folder first

- **Page mockups** (use or improve the matching mockup to build a similar page): `brand/mockups/*.jsx`
  (landing, portfolio, screener, stock, app, mobile, charts) and `screens/*.md` (dashboard,
  fund-detail, portfolio, watchlist, settings, recommendations, …).
- **Components / typography / colour / buttons** (always reference for type scale, font colour, and
  button variants — this is the design intent): `components/*.md` (Button, Card, Input, Table, Search,
  Sidebar, Watchlist, Chart, RecommendationCard) and the brand guide `brand/README.md`.
- `figma/`, `html/` — Figma handoff notes + rendered HTML mockups; visual reference.

## This design is already Geist/warm (no token conflict)

The brand guide is **Geist Sans + Geist Mono + Instrument Serif** with a fixed palette (Deep Navy,
Royal Blue `#1E5EFF`, Emerald, Cyan, Amber, Red). That matches the stack lock, so there is **nothing
to retokenize** — the old "Manrope/cool, retokenize before use" warning is retired (those competing
sets were deleted 2026-06-06; see below).

## Implementation mechanism (what ships)

- **Design tokens:** `frontend/styles/tokens.json` (hand-maintained master) → `frontend/scripts/gen-tokens.mjs`
  → `frontend/src/styles/tokens.css`, `frontend/tailwind.config.js`, `frontend/tailwind.tokens.cjs`
  (never hand-edit the generated files). If the live tokens drift from this brand guide, reconcile
  **toward the brand guide**.
- **Components:** reuse `frontend/src/components/` (catalog: `frontend/src/components/README.md`).
- **Brand assets (logos/favicons):** `frontend/public/brand/`.
- **Alignment record:** `../project-state/CANONICAL_DESIGN_SYSTEM_ALIGNMENT.md`. **UI build rules:** `../../agent.md`.

## What overrides this design (compliance, not stack — always wins)

1. **SEBI advisory boundary** — the palette labels Emerald/Amber/Red as "Buy/Hold/Sell signals" and
   `RecommendationCard` carries advisory verbs. **Translate those to educational labels
   (`in_form/on_track/off_track/out_of_form/insufficient_data`); never copy the advisory verbs.**
2. **No numeric in DOM** — `Chart`/`ScoreRing` show a confidence **band**, never a raw score / weight.

## Do NOT follow the standalone-package build docs

⚠️ `docs/` (01–07 + audits), `claude-code/*-spec.md`, `contracts/` (`openapi.yaml`, `schema.sql`), and
the bootstrap guides (`GETTING_STARTED.md`, `CLAUDE_CODE_STARTER_GUIDE.md`, `nextjs-blueprint/`)
describe the original package's standalone build — a DIFFERENT stack / auth / API / DB than the real
project. **Do NOT follow them.** The real build is `backend/` + `frontend/` per
`../DhanRadar_Architecture_Final.md` + `../DhanRadar_Implementation_Plan.md`.

## Retired (removed 2026-06-06)

Deleted because they conflicted with the canonical `frontend/` tokens (cool palette, advisory verbs,
numeric-score-in-DOM, bearer-capable client) and nothing imported them:

- `design-system/` and `tokens/` — the competing Manrope/cool token sets.
- `reference-impl/` — the pre-compliance component source (superseded by `frontend/src/components/`).
- `brand/tokens.json`, `brand/tokens.css`, `brand/tailwind.config.js` — a stale Geist token mirror
  (canonical lives in `frontend/`).

© 2026 DhanRadar. Research analytics platform — not an investment advisor.
