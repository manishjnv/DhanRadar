# Accessibility

WCAG 2.1 AA as a CI gate. Full spec in /docs/05-frontend-architecture.md §7. Highlights:

- AA contrast on all text; color never the only signal (▲▼ + label with gain/loss & signal bands)
- Visible :focus-visible ring (never stripped); skip-to-content; logical tab order
- Semantic HTML + Radix primitives (Dialog/Popover/Tabs) for built-in ARIA + focus trap
- Charts ship a visually-hidden data <table> + <figcaption>; ScoreRing aria-label="Score N of 100, <signal>"
- ≥44×44 targets; ≥16px inputs; prefers-reduced-motion + prefers-color-scheme honored
- Forms: label/for, aria-describedby errors, role=alert live regions
- CI: eslint-plugin-jsx-a11y + axe/Playwright + Lighthouse a11y budget; manual SR pass per release
