# DhanRadar — Brand Kit v1.0

Wealth, scanned. Spot better investments before the crowd.

---

## Logo files

| File | Use |
|---|---|
| `logo-primary.svg` | Default — full-color gradient mark + navy wordmark. Use on light/neutral backgrounds. |
| `logo-mono-light.svg` | Monochrome black-on-light. Use when color reproduction is unreliable (print, fax, watermarks). |
| `logo-mono-dark.svg` | Logo for dark UI surfaces. Wordmark in off-white. |
| `icon.svg` | Mark only, 64×64. Use for app icons, social profile pictures, anywhere there's no room for the wordmark. |
| `favicon.svg` | 32×32 mark. Smaller, simpler — drop into `<link rel="icon" type="image/svg+xml" href="favicon.svg">`. |

### Clear space
Minimum clear space around the lockup = the height of the **D** glyph on all sides.

### Minimum size
- Lockup: 80px wide on screen, 0.75" in print.
- Icon-only: 16px on screen.

---

## Favicons & app icons

| File | Size | Use |
|---|---|---|
| `favicon.svg` | scalable | Modern browsers (preferred) |
| `favicon-16.png` | 16×16 | Browser tab fallback |
| `favicon-32.png` | 32×32 | Standard favicon |
| `favicon-48.png` | 48×48 | Windows tiles |
| `apple-touch-icon.png` | 180×180 | iOS home screen |
| `android-chrome-192.png` | 192×192 | Android |
| `android-chrome-512.png` | 512×512 | Android splash, PWA |
| `app-icon-1024.png` | 1024×1024 | App Store submission |
| `og-image.png` | 1200×630 | Open Graph / social sharing |

### `<head>` snippet

```html
<link rel="icon" type="image/svg+xml" href="/brand/favicon.svg"/>
<link rel="icon" type="image/png" sizes="32x32" href="/brand/favicon-32.png"/>
<link rel="apple-touch-icon" sizes="180x180" href="/brand/apple-touch-icon.png"/>
<meta property="og:image" content="/brand/og-image.png"/>
<meta property="og:title" content="DhanRadar — Investment intelligence for India"/>
<meta property="og:description" content="Spot better investments before the crowd. Score, screen and analyze 4,200+ stocks and 2,800 mutual funds."/>
```

---

## Color

| Token | Hex | Role |
|---|---|---|
| Deep Navy | `#0B1F3A` | Primary — trust anchor, wordmark, footer |
| Royal Blue | `#1E5EFF` | Action — primary CTAs, links, focus |
| Emerald | `#00B386` | Positive — gains, Buy signals (light mode) |
| Emerald Dark | `#1FD79A` | Positive — dark mode |
| Cyan | `#00C2FF` | Info, highlights, secondary accent |
| Amber | `#F5A623` | Warning, Hold, caution |
| Red | `#E5484D` | Negative — losses, Sell, errors |

**Rule of thumb:** Don't introduce new colors. Every UI element should be expressible in `--text`, `--text-muted`, `--surface`, `--border`, or one of the seven brand colors above.

---

## Typography

- **Geist Sans** — UI, headlines, body. Weights: 300, 400, 500, 600, 700.
- **Geist Mono** — every numeric value, ticker symbols, data labels, kbd shortcuts. Tabular numbers (`font-feature-settings: 'tnum'`) ON by default.
- **Instrument Serif (italic)** — editorial accents only. Use sparingly: one or two words per headline.

**Never** mix Inter, Roboto, or system-default sans-serifs into product surfaces.

---

## Voice & tone

| We are | We are not |
|---|---|
| Calm | Hype-y |
| Data-first | Vague |
| Plain-English | Jargon-heavy |
| Confident | Cocky |
| Respectful of beginners | Condescending |

**Microcopy examples:**
- ✅ "DhanRadar Score combines valuation, growth, quality, momentum and risk."
- ❌ "🚀 Our AI-powered moonshot algorithm crushes the market 💯"
- ✅ "Spot better investments before the crowd."
- ❌ "Beat Wall Street at its own game."

---

## Files in this kit

```
brand/
├── README.md                     ← you are here
├── logo-primary.svg              ← default lockup
├── logo-mono-light.svg
├── logo-mono-dark.svg
├── icon.svg                      ← mark only
├── favicon.svg
├── favicon-16.png · -32 · -48
├── apple-touch-icon.png          ← 180×180
├── android-chrome-192.png · -512
├── app-icon-1024.png             ← App Store
├── og-image.png                  ← 1200×630 social share
├── tokens.json                   ← all tokens, framework-agnostic
├── tokens.css                    ← CSS custom properties
└── tailwind.config.js            ← Tailwind preset
```

---

© 2026 DhanRadar Tech Pvt. Ltd. Markets carry risk. DhanRadar is a research analytics product, not an investment advisor.
