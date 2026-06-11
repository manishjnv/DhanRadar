/**
 * /learn/concepts/[slug] — Single concept-explainer page (C1).
 *
 * Server Component (async); NOT inside (app) route group → no AuthGuard.
 * Chrome (header + standing Disclaimer) provided by MaybeShell.
 *
 * SEO acquisition asset: per-concept metadata via generateMetadata.
 * Returns Next.js notFound() on 404 from the API.
 * Compliance (#9): contextual DisclosureBundle + standing <Disclaimer/>.
 */
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { ConceptArticle } from '@/components/concepts/ConceptArticle';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { fetchConcept } from '@/features/learn/concepts-api';

// Render per-request (SSR), never statically prerendered at build — the page
// fetches the backend, which is not reachable during `next build` (see RCA
// 2026-06-10 "SSR build-time fetch ECONNREFUSED"). Still fully server-rendered
// HTML for crawlers (SEO intact).
export const dynamic = 'force-dynamic';

// ---------------------------------------------------------------------------
// Per-concept SEO metadata
// ---------------------------------------------------------------------------
export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const concept = await fetchConcept(params.slug);
  if (!concept) {
    return {
      title: 'Concept not found — DhanRadar',
    };
  }
  return {
    title:       `${concept.title} — DhanRadar Investing Basics`,
    description: concept.summary,
    openGraph: {
      title:       `${concept.title} — DhanRadar Investing Basics`,
      description: concept.summary,
      type:        'article',
      siteName:    'DhanRadar',
    },
  };
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default async function ConceptPage({
  params,
}: {
  params: { slug: string };
}) {
  const concept = await fetchConcept(params.slug);
  if (!concept) notFound();

  return (
    <MaybeShell>
      <ConceptArticle concept={concept} />
    </MaybeShell>
  );
}
