/**
 * learn/concepts — server-safe fetch helpers (Server Components only) (C1).
 *
 * NEVER import this file from a 'use client' component.
 *
 * Mirrors features/learn/api.ts (G8) — kept self-contained rather than imported
 * from it so the C1 lane does not edit the G8 lane's file; the base-resolution
 * logic must stay identical to api.ts.
 *
 * Base URL resolution (architecture non-negotiable #6: base path /api/v1):
 * these fetches run in a SERVER COMPONENT, so the base MUST be an ABSOLUTE
 * origin (a relative '/api/v1' cannot be fetched server-side — Node's fetch
 * throws "Failed to parse URL"):
 *   - INTERNAL_API_URL  — prod: the backend on the internal Docker network,
 *                         e.g. http://dhanradar-fastapi:8000/api/v1 (set on the
 *                         nextjs container at deploy).
 *   - an ABSOLUTE NEXT_PUBLIC_API_URL, if one is configured.
 *   - http://localhost:8000/api/v1 — local `npm run dev` default.
 *
 * Compliance (#1): no advisory verbs in types. (#9): disclosure fields threaded
 * through so pages can render DisclosureBundle + Disclaimer.
 */

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
        `[learn/concepts-api] server API base must end with "/api/v1" (got "${v}"). ` +
          'The /api/v1 prefix is an architecture non-negotiable.',
      );
    }
    return v.replace(/\/$/, '');
  }
  return 'http://localhost:8000/api/v1';
}

const API_BASE = _resolveServerApiBase();

// ---------------------------------------------------------------------------
// Types — mirror the /learn/concepts backend contract exactly.
// ---------------------------------------------------------------------------

/** One concept card as returned from GET /learn/concepts (list). */
export interface ConceptSummary {
  slug:     string;
  title:    string;
  summary:  string;
  category: string;
}

/** Full concept as returned from GET /learn/concepts/{slug}. */
export interface ConceptDetail extends ConceptSummary {
  body_md:            string;
  updated_at:         string;
  disclosure:         string;
  not_advice:         string;
  disclaimer_version: string;
}

/** Envelope returned from GET /learn/concepts. */
export interface ConceptListResponse {
  concepts:           ConceptSummary[];
  disclosure:         string;
  not_advice:         string;
  disclaimer_version: string;
}

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

/** Shared fetch options — 5-min ISR revalidation (pages set force-dynamic). */
const FETCH_OPTS: RequestInit = { next: { revalidate: 300 } } as RequestInit;

/**
 * Fetch the concept list. Accepts an optional category query param.
 */
export async function fetchConcepts(params?: {
  category?: string;
}): Promise<ConceptListResponse> {
  const qs = new URLSearchParams();
  if (params?.category) qs.set('category', params.category);
  const query = qs.toString() ? `?${qs.toString()}` : '';
  const res = await fetch(`${API_BASE}/learn/concepts${query}`, FETCH_OPTS);
  if (!res.ok) {
    throw new Error(`fetchConcepts: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<ConceptListResponse>;
}

/**
 * Fetch a single concept by slug.
 * Returns null on 404 so the page can call notFound().
 */
export async function fetchConcept(
  slug: string,
): Promise<ConceptDetail | null> {
  const res = await fetch(`${API_BASE}/learn/concepts/${encodeURIComponent(slug)}`, FETCH_OPTS);
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`fetchConcept(${slug}): ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<ConceptDetail>;
}
