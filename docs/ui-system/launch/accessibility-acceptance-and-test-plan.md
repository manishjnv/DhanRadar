# Accessibility Acceptance & Test Plan (F11, F19)

## Acceptance criteria (WCAG 2.1 AA — CI gate)
- All text AA contrast; large text ≥3:1. **Color never the only signal** (▲▼ + sign; signal band + label).
- Every interactive element keyboard-reachable; visible :focus-visible ring (never stripped); skip-to-content first.
- **Charts:** each ships a visually-hidden `<table>` of data + `<figcaption>` takeaway; ScoreRing `aria-label="Score N of 100, <signal>"`.
- Forms: label/for, aria-describedby errors, role=alert live regions; inputs ≥16px (no iOS zoom).
- Targets ≥44×44 mobile. Honor `prefers-reduced-motion` (F19) and `prefers-color-scheme`.

## Test plan
- **Automated (CI):** eslint-plugin-jsx-a11y (lint), axe-core via Playwright on every screen, Lighthouse a11y budget ≥ 95. Build fails below budget.
- **Manual (per release):** screen-reader pass (VoiceOver + NVDA) on critical flows (signup, research, watchlist, assistant, checkout); keyboard-only walkthrough.
- **i18n (F19):** all copy via i18n keys from day 1 (Hindi-first ready); validate RTL-safe layout primitives even if not launched.

## Launch gate (P1)
- [ ] axe + Lighthouse budgets green in CI
- [ ] Manual SR pass on critical flows
- [ ] reduced-motion + i18n keys validated
