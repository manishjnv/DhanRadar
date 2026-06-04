# App Router Structure

```
app/
  (marketing)/  page.tsx pricing/ stocks/[symbol]/ funds/[symbol]/ blog/[slug]/ layout.tsx
  (app)/        dashboard/ portfolio/ watchlist/ screener/ assistant/ settings/ layout.tsx (auth guard)
  (admin)/      ... (role-gated shell)
  api/          route handlers (BFF)
  layout.tsx manifest.ts sitemap.ts robots.ts error.tsx not-found.tsx
```
Marketing = SSR/ISR (SEO). App = dynamic, auth-guarded. generateMetadata per route. JSON-LD on public surfaces.
