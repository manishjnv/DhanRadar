/**
 * learn/tax — server-safe fetch helpers (Server Components only).
 *
 * NEVER import this file from a 'use client' component.
 *
 * Base URL resolution (architecture non-negotiable #6: base path /api/v1):
 *   - Server-side: NEXT_PUBLIC_API_URL must end with /api/v1 when set.
 *     In production the SSR container hits the backend directly via the internal
 *     Docker network; during dev Next.js rewrites /api/v1 → localhost backend.
 *     We replicate the same base-resolution logic as apiClient.ts so every
 *     environment works without a hardcoded localhost.
 *   - All fetches use { next: { revalidate: 300 } } — fresh content every 5 min
 *     for crawlers while avoiding per-request waterfalls. Pass force-dynamic
 *     or revalidate:0 at the page level if needed.
 *
 * Compliance (#1): no advisory verbs in types. (#9): disclosure fields threaded
 * through so pages can render DisclosureBundle + Disclaimer.
 */

// ---------------------------------------------------------------------------
// Base URL — these fetches run in a SERVER COMPONENT, so the base MUST be an
// ABSOLUTE origin. A relative '/api/v1' (what the browser apiClient uses, routed
// by the Cloudflare tunnel) cannot be fetched server-side — Node's fetch throws
// "Failed to parse URL". So SSR uses its own absolute base:
//   - INTERNAL_API_URL  — prod: the backend on the internal Docker network,
//                         e.g. http://dhanradar-fastapi:8000/api/v1 (set on the
//                         nextjs container at deploy; see docs/features/education.md).
//   - an ABSOLUTE NEXT_PUBLIC_API_URL, if one is configured.
//   - http://localhost:8000/api/v1 — local `npm run dev` default.
// Each candidate must still carry the non-negotiable /api/v1 base (non-neg #6).
// ---------------------------------------------------------------------------
function _resolveServerApiBase(): string {
  const candidates = [
    process.env.INTERNAL_API_URL,
    process.env.NEXT_PUBLIC_API_URL,
  ];
  for (const raw of candidates) {
    const v = raw?.trim();
    if (!v || !/^https?:\/\//.test(v)) continue; // relative URLs are unusable server-side
    if (!/\/api\/v1\/?$/.test(v)) {
      throw new Error(
        `[learn/api] server API base must end with "/api/v1" (got "${v}"). ` +
          'The /api/v1 prefix is an architecture non-negotiable.',
      );
    }
    return v.replace(/\/$/, '');
  }
  return 'http://localhost:8000/api/v1';
}

const API_BASE = _resolveServerApiBase();

// ---------------------------------------------------------------------------
// Types — mirror the /learn/tax backend contract exactly.
// ---------------------------------------------------------------------------

/** One article card as returned from GET /learn/tax (list). */
export interface TaxArticleSummary {
  slug:              string;
  title:             string;
  summary:           string;
  category:          string;
  fy_label:          string;
}

/** Full article as returned from GET /learn/tax/{slug}. */
export interface TaxArticleDetail extends TaxArticleSummary {
  body_md:      string;
  source_note:  string | null;
  updated_at:   string;
  disclosure:   string;
  not_advice:   string;
  disclaimer_version: string;
}

/** One key date in the tax calendar. */
export interface TaxKeyDate {
  label: string;
  date:  string;
  note:  string;
}

/** Response from GET /learn/tax/calendar. */
export interface TaxCalendar {
  fy_label:   string;
  fy_start:   string;
  fy_end:     string;
  key_dates:  TaxKeyDate[];
  elss_note:  string;
  disclosure: string;
  not_advice: string;
  disclaimer_version: string;
}

/** Envelope returned from GET /learn/tax. */
export interface TaxArticleListResponse {
  articles:           TaxArticleSummary[];
  disclosure:         string;
  not_advice:         string;
  disclaimer_version: string;
}

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

/** Shared fetch options — 5-min ISR revalidation. */
const FETCH_OPTS: RequestInit = { next: { revalidate: 300 } } as RequestInit;

/**
 * Fetch the tax article list.
 * Accepts optional category / fy query params.
 */
export async function fetchTaxArticles(params?: {
  category?: string;
  fy?: string;
}): Promise<TaxArticleListResponse> {
  const qs = new URLSearchParams();
  if (params?.category) qs.set('category', params.category);
  if (params?.fy)       qs.set('fy', params.fy);
  const query = qs.toString() ? `?${qs.toString()}` : '';
  const res = await fetch(`${API_BASE}/learn/tax${query}`, FETCH_OPTS);
  if (!res.ok) {
    throw new Error(`fetchTaxArticles: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<TaxArticleListResponse>;
}

/**
 * Fetch a single tax article by slug.
 * Returns null on 404 so the page can call notFound().
 */
export async function fetchTaxArticle(
  slug: string,
): Promise<TaxArticleDetail | null> {
  const res = await fetch(`${API_BASE}/learn/tax/${encodeURIComponent(slug)}`, FETCH_OPTS);
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`fetchTaxArticle(${slug}): ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<TaxArticleDetail>;
}

/**
 * Fetch the tax calendar.
 */
export async function fetchTaxCalendar(): Promise<TaxCalendar> {
  const res = await fetch(`${API_BASE}/learn/tax/calendar`, FETCH_OPTS);
  if (!res.ok) {
    throw new Error(`fetchTaxCalendar: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<TaxCalendar>;
}
