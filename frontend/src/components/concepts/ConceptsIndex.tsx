/**
 * ConceptsIndex — presentational index for the /learn/concepts library (C1).
 *
 * Pure server-safe presentational component (no hooks, no fetch) so it is
 * directly unit-testable in vitest/jsdom; the async Server Component page
 * fetches and passes `data`. Groups concepts by category in seed order.
 *
 * Compliance (#9): renders the contextual DisclosureBundle from the API
 * payload. The standing <Disclaimer/> is provided by MaybeShell at page level.
 */
import Link from 'next/link';
import { Card, CardBody } from '@/components/ui/Card';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import type { ConceptListResponse, ConceptSummary } from '@/features/learn/concepts-api';

function ConceptCard({ concept }: { concept: ConceptSummary }) {
  return (
    <Link
      href={`/learn/concepts/${concept.slug}`}
      className="block group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded-lg"
    >
      <Card className="hover:shadow-md transition-shadow">
        <CardBody>
          <h3 className="text-h3 font-medium text-ink group-hover:text-royal transition-colors leading-snug">
            {concept.title}
          </h3>
          <p className="text-small text-ink-secondary mt-1 line-clamp-2">
            {concept.summary}
          </p>
        </CardBody>
      </Card>
    </Link>
  );
}

export function ConceptsIndex({ data }: { data: ConceptListResponse }) {
  // Group by category, preserving the API's (sort_order) sequence.
  const categories: string[] = [];
  const byCategory = new Map<string, ConceptSummary[]>();
  for (const c of data.concepts) {
    if (!byCategory.has(c.category)) {
      byCategory.set(c.category, []);
      categories.push(c.category);
    }
    byCategory.get(c.category)!.push(c);
  }

  return (
    <>
      {data.concepts.length === 0 ? (
        <Card>
          <CardBody>
            <p className="text-small text-ink-muted text-center py-4">
              Concept explainers are being prepared. Check back shortly.
            </p>
          </CardBody>
        </Card>
      ) : (
        <div className="space-y-8">
          {categories.map((category) => (
            <section key={category} aria-label={category}>
              <h2 className="text-caption text-ink-muted uppercase tracking-wide mb-3">
                {category}
              </h2>
              <div className="space-y-4" role="list" aria-label={`${category} concepts`}>
                {byCategory.get(category)!.map((concept) => (
                  <div key={concept.slug} role="listitem">
                    <ConceptCard concept={concept} />
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Footer — disclosure (non-negotiable #9)                             */}
      {/* ------------------------------------------------------------------ */}
      <footer className="mt-10 space-y-2">
        <DisclosureBundle
          disclosure={data.disclosure}
          notAdvice={data.not_advice}
        />
        {/* Standing <Disclaimer/> is rendered by MaybeShell. */}
      </footer>
    </>
  );
}
