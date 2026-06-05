# DhanRadar — Design Tokens

Single source of truth. Branding is **locked** — do not change brand colors, type, or logo.

## Files
| File | Format | Use |
|---|---|---|
| colors.json | JSON | brand/semantic/neutral palettes (light+dark) |
| typography.json | JSON | families + type scale |
| spacing.json | JSON | 4px grid scale |
| radius.json | JSON | corner radii |
| elevation.json | JSON | shadow scale |
| motion.json | JSON | durations + easings |
| themes.json | JSON | light/dark neutrals, signal bands, breakpoints, z-index |
| tailwind.config.js | JS | Tailwind preset (consumes CSS vars) |
| css-variables.css | CSS | drop-in custom properties (.theme-light/.theme-dark) |

## Brand colors (locked)
- Deep Navy `#0B1F3A` · Electric Blue `#2563EB` · Emerald `#10B981`
- Semantic: success #10B981 · warning #F59E0B · error #EF4444 · info #2563EB

## Type
- Display: **Manrope** (h1–h3) · Body: **Inter** · Numeric: **JetBrains Mono** (tnum)

## Score signal bands
- ≥85 Strong Buy · ≥70 Buy · ≥55 Hold · ≥40 Caution · <40 Avoid

## Pipeline
Figma Variables → Style Dictionary → `tokens.json` → `css-variables.css` + `tailwind.config.js`. Theme switch = class on `<html>`; Tailwind utilities resolve to CSS vars, so retheme has zero render cost.
