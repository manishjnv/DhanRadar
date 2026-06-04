# Design Token Integration

Style Dictionary builds /tokens → styles/tokens.css (CSS vars per theme) + tailwind.config.ts (preset reading vars). Tailwind utilities resolve to var(--…); theme = class on <html> (theme-light/theme-dark), zero re-render. Fonts via next/font (self-host Manrope/Inter/JetBrains Mono). No magic numbers (ESLint). Full: /docs/05 §5.
