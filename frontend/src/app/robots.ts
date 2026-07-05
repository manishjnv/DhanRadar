/**
 * robots.txt — points crawlers at the fund-page sitemap chunks.
 *
 * Next.js's `generateSitemaps()` (used in app/sitemap.ts) does NOT auto-generate
 * a combined index at `/sitemap.xml` — per Next.js's own docs, it only produces
 * per-chunk routes at `/sitemap/[id].xml` (confirmed: `next build`'s route table
 * lists `/sitemap/[__metadata_id__]` with no separate `/sitemap.xml` entry, and
 * a live request to `/sitemap.xml` 404s — this is documented, expected Next.js
 * behavior, not a bug). Without this file, the chunked sitemaps built for the
 * SEO wedge (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §18.6) would be
 * undiscoverable by search engines, defeating their purpose. The standard fix is
 * exactly this: list every chunk explicitly as a `Sitemap:` directive in
 * robots.txt (Google/Bing both crawl multiple `Sitemap:` lines).
 *
 * Reuses sitemap.ts's own `collectAllIsins()`/`sitemapChunkCount()` so the chunk
 * count here can never drift out of sync with what `generateSitemaps()` itself
 * produces. Same build-time-safety posture as sitemap.ts: `collectAllIsins()`
 * degrades to an empty list (and therefore 1 chunk) on any backend failure,
 * so `next build` never touches the backend and never fails.
 */
import type { MetadataRoute } from 'next';
import { collectAllIsins, sitemapChunkCount } from './sitemap';
import { SITE_URL } from '@/features/mf/fundMetadata';

export const dynamic = 'force-dynamic';

export default async function robots(): Promise<MetadataRoute.Robots> {
  const isins = await collectAllIsins();
  const count = sitemapChunkCount(isins.length);
  const sitemaps = Array.from({ length: count }, (_, id) => `${SITE_URL}/sitemap/${id}.xml`);

  return {
    rules: { userAgent: '*', allow: '/' },
    sitemap: sitemaps,
  };
}
