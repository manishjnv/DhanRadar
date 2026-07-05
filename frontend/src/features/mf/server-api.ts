/**
 * mf/server-api — server-only fetch helpers for the Fund Detail SSR core
 * (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §18.6). Server Components / metadata
 * route files ONLY — NEVER import this from a 'use client' component.
 *
 * Base URL resolution deliberately mirrors `_resolveServerApiBase()` in
 * frontend/src/features/learn/api.ts (the already-battle-tested pattern in this
 * repo for resolving the server-side backend base). That function is not
 * exported, so the same small resolver is duplicated here rather than imported —
 * credit: frontend/src/features/learn/api.ts.
 *
 * Caching: every fetch below sets `next: { revalidate: 3600 }` — this is
 * "daily-ish" data (nightly NAV/rank refresh), not something recomputed every
 * request. This is a PER-FETCH cache directive, independent of the route's own
 * `dynamic` rendering mode — Next.js 14.2 honors it even when the calling route
 * is `force-dynamic` (verified: vercel/next.js test/e2e/app-dir/app-static/app/
 * force-dynamic-fetch-cache/revalidate/page.js — "should infer a fetch cache of
 * 'force-cache' when force-dynamic is used on a fetch with revalidate"). See
 * app/mf/fund/[isin]/page.tsx and app/sitemap.ts for the full reasoning.
 *
 * Every helper below swallows fetch/parse errors and degrades to an empty/null
 * result rather than throwing — callers treat that as "not found" / "no data
 * yet", never a 500. This also means a transient backend hiccup (or the backend
 * being completely unreachable, as it always is during `next build`) can never
 * fail a caller that guards against it.
 */
import type { DataEnvelope } from '@/data/envelope';
import type { FundCategoriesResponse, FundCategory, FundExplorerResponse, FundHead } from './types';

function _resolveServerApiBase(): string {
  const candidates = [process.env.INTERNAL_API_URL, process.env.NEXT_PUBLIC_API_URL];
  for (const raw of candidates) {
    const v = raw?.trim();
    if (!v || !/^https?:\/\//.test(v)) continue; // relative URLs are unusable server-side
    if (!/\/api\/v1\/?$/.test(v)) {
      throw new Error(
        `[mf/server-api] server API base must end with "/api/v1" (got "${v}"). ` +
          'The /api/v1 prefix is an architecture non-negotiable.',
      );
    }
    return v.replace(/\/$/, '');
  }
  return 'http://localhost:8000/api/v1';
}

const API_BASE = _resolveServerApiBase();

/** ~1h freshness window for the server-side fetches below (see file header). */
const REVALIDATE_SECONDS = 3600;

/**
 * `fund.head` server fetch (single ISIN) — GET /mf/fund/{isin}. Returns null on
 * 404 (unknown ISIN) or on ANY fetch failure; callers (generateMetadata / the
 * page body) treat null as "render notFound()".
 */
export async function fetchFundHeadServer(isin: string): Promise<FundHead | null> {
  try {
    const res = await fetch(`${API_BASE}/mf/fund/${isin}`, {
      next: { revalidate: REVALIDATE_SECONDS },
    });
    if (!res.ok) return null;
    const env = (await res.json()) as DataEnvelope<FundHead>;
    return env.data;
  } catch {
    return null;
  }
}

/** GET /mf/funds/categories — sitemap category enumeration. Empty array on any
 *  failure (build-time-safe; see app/sitemap.ts doc comment). */
export async function fetchFundCategoriesServer(): Promise<FundCategory[]> {
  try {
    const res = await fetch(`${API_BASE}/mf/funds/categories`, {
      next: { revalidate: REVALIDATE_SECONDS },
    });
    if (!res.ok) return [];
    const body = (await res.json()) as FundCategoriesResponse;
    return body.categories;
  } catch {
    return [];
  }
}

/** One page of GET /mf/funds?category=X&page=N&limit=L — sitemap ISIN
 *  enumeration. Empty result on any failure (same build-time-safe posture). */
export async function fetchFundIsinsPageServer(
  category: string,
  page: number,
  limit: number,
): Promise<{ isins: string[]; total: number }> {
  try {
    const res = await fetch(
      `${API_BASE}/mf/funds?category=${encodeURIComponent(category)}&page=${page}&limit=${limit}`,
      { next: { revalidate: REVALIDATE_SECONDS } },
    );
    if (!res.ok) return { isins: [], total: 0 };
    const body = (await res.json()) as FundExplorerResponse;
    return { isins: body.funds.map((f) => f.isin), total: body.total };
  } catch {
    return { isins: [], total: 0 };
  }
}
