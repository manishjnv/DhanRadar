# Canonical Design System Alignment

**Stage 1 — Contract Reconciliation. Documentation only; no token files or components changed.**
**Date:** 2026-06-05
**Decision applied:** **D1 — existing DhanRadar branding is the single source of truth** (Geist typography, existing warm palette, existing frontend token structure). No second design language; no parallel token systems; retire duplicates.

---

## 0. Root cause being fixed

The UI package ships **three** token sets under one `--dr-*` prefix that resolve to **different** fonts and hexes:
- `docs/ui-system/brand/` — Geist + **warm** palette (`royal #1E5EFF`, `emerald #00B386`…), keys `royal`, `ink-secondary`.
- `docs/ui-system/design-system/` — Manrope/Inter + **cool** palette (`blue #2563EB`, `emerald #10B981`…), keys `blue`, `ink-2`.
- `docs/ui-system/tokens/` — duplicate of `design-system/` (cool/Manrope).

The existing repo (`frontend/styles/tokens.json`, `frontend/app/tokens.css`, `frontend/tailwind.config.js`) is an **exact copy of `brand/`** (Geist/warm). But the UI package's **buildable components, Figma, and screen specs are authored in `design-system/` (Manrope/cool)** — so they will not compile or render correctly against the canonical tokens.

**D1 resolves this:** the **brand/Geist/warm** set wins. Everything authored in Manrope/cool must be **retokenized** to it.

---

## 1. Winning token source (canonical)

**Canonical source of truth = the existing repo token files, which mirror `docs/ui-system/brand/`:**
- `frontend/styles/tokens.json` — framework-agnostic tokens.
- `frontend/app/tokens.css` — CSS custom properties (`--dr-*` + theme-scoped).
- `frontend/tailwind.config.js` — Tailwind theme mapping.

**Canonical identity:**
- **Typography:** Geist Sans (UI/body/headlines), Geist Mono (all numerics/tickers/data, tabular `tnum`), Instrument Serif (editorial accents, sparingly).
- **Palette (warm, "locked"):** Deep Navy `#0B1F3A`, Royal Blue `#1E5EFF`, Emerald `#00B386` (light) / `#1FD79A` (dark), Cyan `#00C2FF`, Amber `#F5A623`, Red `#E5484D`.
- **Tailwind color keys:** `navy`, `royal`, `emerald{DEFAULT,dark}`, `cyan`, `amber`, `red{DEFAULT,dark}`; surfaces `bg`, `surface`, `surface-2`, `surface-3`; text `ink`, `ink-secondary`, `ink-muted`, `ink-faint`; borders `line`, `line-strong`.
- **CSS var prefix:** `--dr-*` for brand/spacing/radii; unprefixed theme-scoped vars (`--bg`, `--surface`, `--text`, `--positive`, `--negative`…) drive light/dark via the `class` strategy.

**Canonical generation target (Stage 2, not now):** a single token pipeline emits all three repo files from one source, so they can never drift again. Until then, `frontend/styles/tokens.json` is the hand-maintained master.

---

## 2. Token mapping (Manrope/cool → canonical Geist/warm)

Every component/screen/Figma reference authored against `design-system/`/`tokens/` must remap:

| Concern | UI-package design-system (LOSE) | Canonical brand (WIN) |
|---|---|---|
| Body/UI font | Inter | **Geist Sans** |
| Display font | Manrope | **Geist Sans** (no separate display family; weight-based hierarchy) |
| Mono font | JetBrains Mono | **Geist Mono** |
| Editorial accent | (none) | **Instrument Serif** (italic, sparing) |
| Primary action color key | `blue` (`#2563EB`, +50/600/700 shades) | **`royal` (`#1E5EFF`)** |
| Positive | `emerald #10B981` / dark `#22D3A6` | **`emerald #00B386` / dark `#1FD79A`** |
| Cyan | `#06B6D4` | **`#00C2FF`** |
| Amber | `#F59E0B` | **`#F5A623`** |
| Red/negative | `#EF4444` | **`#E5484D`** |
| Secondary text key | `ink-2` | **`ink-secondary`** |
| Spacing scale | 0–32 (13 stops) | brand scale (1–16, 8 stops) — **extend brand if a component needs more, but keep brand naming** |
| Radius | sm6/md8/lg12/xl16/2xl20 | brand sm4/md8/lg12/xl14/2xl18 |
| Shadows | xs/sm/md/lg/xl + ring | brand sm/md/lg — **add xs/xl/ring to brand if needed** (additive, not a fork) |
| Multi-shade blue (50/600/700) | present | **derive tints from `royal` only if a component requires; do not import the cool ramp** |

**Note on `blue` opacity ring:** UI-package `Button.tsx` uses `ring-blue/40`. Remap to `ring-royal/40`; ensure `royal` is exposed as a Tailwind color (it is) so the `/40` opacity modifier works.

---

## 3. Component mapping (UI-package reference-impl → canonical)

The UI package's buildable components are the starting point but must be retokenized before they compile against canonical Tailwind.

| Component (`docs/ui-system/reference-impl` / `components`) | Assumes (LOSE) | Retokenize to (WIN) | Effort |
|---|---|---|---|
| `ui/Button.tsx` | `bg-blue`, `hover:bg-blue-700`, `ring-blue/40`, `bg-ink`, `text-bg`, `positive`/`negative` | `bg-royal`, `hover:bg-royal/90` (or define `royal.dark`), `ring-royal/40`, `bg-ink`, semantic `positive`/`negative` (already CSS-var driven) | low |
| `ui/Card.tsx` | `surface-2/3`, `line` | same keys exist in brand — verify font + radius | low |
| `charts/ScoreRing.tsx` | numeric score ring, cool palette | **two changes:** (a) palette→warm; (b) **render confidence band, not raw numeric score, on ungated views** (architecture "no numeric in DOM") | medium (compliance) |
| `lib/cn.ts`, `lib/apiClient.ts`, `lib/queryKeys.ts` | tokenless | keep as-is; `apiClient` must use cookie auth + `/api/v1` (see OpenAPI doc) | low |
| `tailwind.preset.ts` | cool/Manrope subset | **discard**; regenerate from canonical `frontend/tailwind.config.js` | n/a |
| `/components/*.md` specs (Button, Card, Chart, Input, Search, Sidebar, Table, Watchlist, RecommendationCard) | cool/Manrope, may use advisory copy | retokenize + relabel advisory terms (`RecommendationCard` → educational signal labels) | medium |
| `/screens/*.md` (13 specs) + `/figma/*` (10 docs) + `/html/*` mockups | Manrope/cool throughout | retokenize references; treat as visual reference only, rebuilt in canonical tokens | medium-high (bulk, mechanical) |

**RecommendationCard special note:** its copy/labels must follow non-negotiable #2 — no `strong_buy/buy/hold/avoid`; use `in_form/on_track/off_track/out_of_form` + confidence band.

---

## 4. Retokenization plan (sequenced for Stage 2 — not executed here)

1. **Freeze the canonical source.** Confirm `frontend/styles/tokens.json` is complete; add any missing additive tokens (extra spacing stops, xs/xl shadow, ring) **under brand naming**. One commit, design-review only.
2. **Build the token pipeline.** Single source → `tokens.json` + `tokens.css` + `tailwind.config.js` (so drift is impossible). Mechanical; Tier-2/Sonnet candidate.
3. **Retokenize reference-impl components** (Button, Card, ScoreRing first — they unblock everything). Tier-1 Sonnet per component; Opus diff-review. ScoreRing change is compliance-relevant (band not number).
4. **Port component specs** (`/components/*.md`) into canonical-tokened versions under `docs/features/` or `frontend` storybook; relabel advisory copy. Bulk, parallel Sonnet.
5. **Rebuild screens** in canonical tokens, in architecture phase order (MF-first), creating missing screens (CAS upload) in-system.
6. **Retire duplicates** (see §5) only after 1–4 land and nothing imports them.

---

## 5. Deprecated / retired design assets

After reconciliation, these are **retired** (kept in git history; removed from the active source-of-truth set so no one builds against them):

| Asset | Action | Reason |
|---|---|---|
| `docs/ui-system/design-system/` (tokens.json, css-variables.css, tailwind.config.js, figma-variables.json) | **RETIRE** | Manrope/cool — competes with canonical; duplicate of `tokens/` |
| `docs/ui-system/tokens/` (colors/typography/…/tailwind/css) | **RETIRE** | Manrope/cool duplicate of `design-system/` |
| `docs/ui-system/reference-impl/tailwind.preset.ts` | **DISCARD** | cool/Manrope subset; regenerated from canonical |
| `docs/ui-system/figma/*` Manrope/cool variable references | **SUPERSEDE** | retokenized; Figma variables re-exported from canonical |
| `docs/ui-system/html/*` mockups | **REFERENCE-ONLY** | visual reference; not a build source |
| `docs/ui-system/brand/` | **KEEP as the upstream mirror** of the canonical repo tokens (Geist/warm) | it *is* the winning set |

**Retirement is documentation-state only in Stage 1.** No files are deleted now; this table is the instruction for Stage 2. Branding remains "locked" — the warm/Geist identity is unchanged; we are removing the competing cool/Manrope set, not altering the brand.

---

## 6. Decisions / confirmations
- **D1 applied** — no open design decision remains. The only judgment calls left are mechanical (which additive tokens to add under brand naming), handled in retokenization step 1.
- **Cross-link:** `RecommendationCard` and `ScoreRing` retokenization must also satisfy the label/numeric rules in `CANONICAL_OPENAPI_ALIGNMENT.md` §5 and `RECOMMENDATION_ENGINE_ALIGNMENT.md` §2.
</content>
