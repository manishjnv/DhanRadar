/**
 * Sitemap — ranked mutual-fund detail pages (`/mf/fund/{isin}`).
 *
 * Scope (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §18.6): fund pages only, not a
 * site-wide sitemap. Chunked via Next.js's built-in `generateSitemaps()` App
 * Router API (a sitemap INDEX + numbered sub-sitemaps, each capped near
 * Google's ~50,000-URL practical limit) rather than hand-rolled XML.
 *
 * Source: the EXISTING public explorer endpoints only — no new backend route.
 *   GET /mf/funds/categories        — enumerate categories
 *   GET /mf/funds?category=X&page=N — page through each category's ranked funds
 * (backend/dhanradar/mf/router.py — `fund_categories` / `fund_explorer_list`).
 *
 * BUILD-TIME SAFETY (docs/rca/README.md G8 — same trap as the fund page):
 * Next's metadata-route loader calls `generateSitemaps()` to enumerate the
 * sitemap `id`s that back this route's static param list — it does this
 * regardless of the `dynamic = 'force-dynamic'` export below, because it needs
 * to know the route shape (`/sitemap/[id].xml`). The backend is unreachable
 * during CI's `next build` (mocks-off job), so `collectAllIsins()` wraps every
 * backend call in try/catch and degrades to an empty list on ANY failure —
 * `generateSitemaps()` then returns a single `{ id: 0 }` chunk and `next build`
 * never fails (verified: `npm run build` with no backend running completes
 * and lists `/sitemap/[__metadata_id__]` in the route table).
 *
 * VERIFIED build behaviour (`.next/prerender-manifest.json` after `npm run
 * build`): `dynamic = 'force-dynamic'` has no effect on this specific route —
 * once `generateSitemaps()` is present, Next.js 14.2 statically prerenders the
 * enumerated chunk(s) as ISR pages rather than rendering per-request, and
 * `"/sitemap/0.xml"` is recorded with `"initialRevalidateSeconds": 3600` (the
 * fetch-level `next: { revalidate: 3600 }` from `features/mf/server-api.ts`
 * propagates to the route's own ISR window). This is the CORRECT outcome for
 * a sitemap, not a workaround: because the empty build-time fallback is only
 * ever the FIRST render, Next regenerates this route in the background on the
 * next request after the 3600s window elapses (or via on-demand revalidation),
 * replacing the empty chunk with the real, backend-sourced ISIN list once the
 * backend is reachable — it never stays frozen at the empty build-time
 * snapshot. `dynamic = 'force-dynamic'` is kept anyway (matches the documented
 * pattern in vercel/next.js test/e2e/app-dir/metadata-dynamic-routes/app/
 * route-config/sitemap.ts and dynamic-in-generate-params/app/sitemap.js) —
 * harmless here, and correct for any future sitemap in this app that does NOT
 * use `generateSitemaps()`.
 *
 * Caching: each backend fetch below sets `next: { revalidate: 3600 }` (see
 * features/mf/server-api.ts) — "daily-ish" data, not recomputed every request.
 * This also means `generateSitemaps()` and each `sitemap({id})` invocation
 * (which both call `collectAllIsins()`) share Next's fetch Data Cache instead
 * of re-crawling every category/page on every call.
 */
import type { MetadataRoute } from 'next';
import { fetchFundCategoriesServer, fetchFundIsinsPageServer } from '@/features/mf/server-api';
import { SITE_URL } from '@/features/mf/fundMetadata';

export const dynamic = 'force-dynamic';

// Headroom under Google's ~50,000-URL practical sitemap limit.
const URLS_PER_SITEMAP = 45_000;
// Matches the /mf/funds `limit` query cap (`le=500`, dhanradar/mf/router.py).
const EXPLORER_PAGE_LIMIT = 500;

async function collectAllIsins(): Promise<string[]> {
  try {
    const categories = await fetchFundCategoriesServer();
    const isins: string[] = [];
    for (const cat of categories) {
      let page = 1;
      for (;;) {
        const { isins: pageIsins, total } = await fetchFundIsinsPageServer(cat.key, page, EXPLORER_PAGE_LIMIT);
        if (pageIsins.length === 0) break;
        isins.push(...pageIsins);
        if (page * EXPLORER_PAGE_LIMIT >= total) break;
        page += 1;
      }
    }
    return isins;
  } catch {
    return [];
  }
}

export async function generateSitemaps() {
  const isins = await collectAllIsins();
  const count = Math.max(1, Math.ceil(isins.length / URLS_PER_SITEMAP));
  return Array.from({ length: count }, (_, id) => ({ id }));
}

export default async function sitemap({ id }: { id: number }): Promise<MetadataRoute.Sitemap> {
  const isins = await collectAllIsins();
  const start = id * URLS_PER_SITEMAP;
  const chunk = isins.slice(start, start + URLS_PER_SITEMAP);

  return chunk.map((isin) => ({
    url: `${SITE_URL}/mf/fund/${isin}`,
    changeFrequency: 'daily',
    priority: 0.7,
  }));
}
