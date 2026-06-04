# Routing Spec

App Router groups: `(marketing)` (public, SSR/ISR, SEO), `(app)` (auth-guarded shell), `(admin)` (role-gated separate shell), `api/` (BFF route handlers: cookies, webhook proxy). Auth guard in group layouts verifies session cookie server-side → redirect. Public instrument pages: `/stocks/[symbol]` ISR (revalidate 300 + on-demand on score recompute). Sitemap/robots generated from catalog; admin disallowed.
