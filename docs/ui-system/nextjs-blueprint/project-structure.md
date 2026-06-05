# Project Structure

```
src/
  app/            # App Router (RSC + routing)
  features/       # feature slices (instrument, portfolio, watchlist, ai, billing, auth, news)
  components/     # shared DS primitives (ui, charts, feedback, layout)
  lib/            # api client, query keys, auth, format, analytics, seo, pwa
  styles/         # globals.css + tokens.css
  hooks/ types/ config/ test/
```
Feature may import components/lib/hooks/types — never another feature internals (ESLint import/no-restricted-paths). Full: /docs/05 §1.
