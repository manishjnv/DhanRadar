/**
 * /learn/concepts — Concept-Explainer library index page (C1).
 *
 * Server Component (async); NOT inside (app) route group → no AuthGuard.
 * Chrome (header + standing Disclaimer) provided by MaybeShell.
 *
 * SEO acquisition asset: fully server-rendered, static metadata.
 * Compliance (#9): DisclosureBundle from API payload + standing <Disclaimer/>.
 */
import type { Metadata } from 'next';
import Link from 'next/link';
import { ConceptsIndex } from '@/components/concepts/ConceptsIndex';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { fetchConcepts } from '@/features/learn/concepts-api';
import { BookOpen } from 'lucide-react';

// Render per-request (SSR), never statically prerendered at build — the page
// fetches the backend, which is not reachable during `next build` (see RCA
// 2026-06-10 "SSR build-time fetch ECONNREFUSED"). Still fully server-rendered
// HTML for crawlers (SEO intact).
export const dynamic = 'force-dynamic';

// ---------------------------------------------------------------------------
// Static SEO metadata
// ---------------------------------------------------------------------------
export const metadata: Metadata = {
  title: 'Investing Basics — DhanRadar',
  description:
    'Plain-language explainers of core investing concepts — risk, volatility, diversification, asset allocation, costs, SIPs, and compounding. Educational content only — not investment advice.',
  openGraph: {
    title:       'Investing Basics — DhanRadar',
    description: 'Plain-language explainers of core investing concepts — risk, volatility, diversification, asset allocation, costs, SIPs, and compounding.',
    type:        'website',
    siteName:    'DhanRadar',
  },
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default async function ConceptsLearnPage() {
  const data = await fetchConcepts();

  return (
    <MaybeShell>
      {/* Page heading */}
      <div className="mb-6">
        <h1 className="text-h2 text-ink">Investing Basics</h1>
        <p className="text-small text-ink-secondary mt-1">
          Plain-language explainers of the concepts behind every portfolio — what they
          are and why they matter.
        </p>
      </div>

      {/* Sibling /learn area link (internal cluster linking) */}
      <div className="mb-6">
        <Link
          href="/learn/tax"
          className="inline-flex items-center gap-2 text-small text-royal hover:text-royal/80 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded"
        >
          <BookOpen size={16} aria-hidden="true" />
          Looking for tax rules? Tax Education
        </Link>
      </div>

      <ConceptsIndex data={data} />
    </MaybeShell>
  );
}
