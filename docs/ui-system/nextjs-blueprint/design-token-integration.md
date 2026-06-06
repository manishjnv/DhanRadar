# Design Token Integration

**Reference only — superseded.** The real token pipeline is `frontend/scripts/gen-tokens.mjs`, building `frontend/styles/tokens.json` → `frontend/src/styles/tokens.css` + `frontend/tailwind.config.js` / `frontend/tailwind.tokens.cjs`. Fonts are **Geist Sans/Mono + Instrument Serif** via `next/font` (NOT Manrope/Inter/JetBrains Mono — that cool stack was retired 2026-06-06). Tailwind utilities resolve to `var(--…)`; theme = class on `<html>` (theme-light/theme-dark). No magic numbers (ESLint).
