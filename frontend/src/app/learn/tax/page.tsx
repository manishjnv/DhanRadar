/**
 * /learn/tax — Tax education index page.
 *
 * Server Component (async); NOT inside (app) route group → no AuthGuard.
 * Chrome (header + standing Disclaimer) provided by MaybeShell.
 *
 * SEO acquisition asset: fully server-rendered, static metadata, ISR 5 min.
 * Compliance (#9): DisclosureBundle from API payload + standing <Disclaimer/>.
 */
import type { Metadata } from 'next';
import Link from 'next/link';
import { Card, CardBody }  from '@/components/ui/Card';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { fetchTaxArticles } from '@/features/learn/api';
import type { TaxArticleSummary } from '@/features/learn/api';
import { CalendarDays }    from 'lucide-react';

// Render per-request (SSR), never statically prerendered at build — the page
// fetches the backend, which is not reachable during `next build`. Still fully
// server-rendered HTML for crawlers (SEO intact).
export const dynamic = 'force-dynamic';

// ---------------------------------------------------------------------------
// Static SEO metadata
// ---------------------------------------------------------------------------
export const metadata: Metadata = {
  title: 'Tax Education — DhanRadar',
  description:
    'Plain-language guides on Indian income-tax rules, ELSS, capital gains, and key FY deadlines. Educational content only — not investment advice.',
  openGraph: {
    title:       'Tax Education — DhanRadar',
    description: 'Plain-language guides on Indian income-tax rules, ELSS, capital gains, and key FY deadlines.',
    type:        'website',
    siteName:    'DhanRadar',
  },
};

// ---------------------------------------------------------------------------
// Article card
// ---------------------------------------------------------------------------
function ArticleCard({ article }: { article: TaxArticleSummary }) {
  return (
    <Link
      href={`/learn/tax/${article.slug}`}
      className="block group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded-lg"
    >
      <Card className="hover:shadow-md transition-shadow">
        <CardBody>
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <h2 className="text-h3 text-ink group-hover:text-royal transition-colors leading-snug">
                {article.title}
              </h2>
              <p className="text-small text-ink-secondary mt-1 line-clamp-2">
                {article.summary}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 mt-3">
            <span className="font-mono text-caption text-ink-muted uppercase tracking-[0.06em]">
              {article.category}
            </span>
            <span className="text-caption text-ink-faint" aria-hidden="true">·</span>
            <span className="font-mono text-caption text-ink-muted tabular-nums">{article.fy_label}</span>
          </div>
        </CardBody>
      </Card>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default async function TaxLearnPage() {
  const data = await fetchTaxArticles();

  return (
    <MaybeShell>
      {/* Page heading */}
      <div className="mb-6">
        <h1 className="text-h2 text-ink">Tax Education</h1>
        <p className="text-small text-ink-secondary mt-1">
          Plain-language guides on Indian income-tax rules, ELSS, capital gains, and FY deadlines.
        </p>
      </div>

      {/* Tax calendar link */}
      <div className="mb-6">
        <Link
          href="/learn/tax/calendar"
          className="inline-flex items-center gap-2 text-small text-royal hover:text-royal/80 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded"
        >
          <CalendarDays size={16} aria-hidden="true" />
          View FY tax calendar and key deadlines
        </Link>
      </div>

      {/* Article list */}
      {data.articles.length === 0 ? (
        <Card>
          <CardBody>
            <p className="text-small text-ink-muted text-center py-4">
              Articles are being updated for the new financial year. Check back shortly.
            </p>
          </CardBody>
        </Card>
      ) : (
        <div className="space-y-4" role="list" aria-label="Tax education articles">
          {data.articles.map((article) => (
            <div key={article.slug} role="listitem">
              <ArticleCard article={article} />
            </div>
          ))}
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Footer — disclosure (non-negotiable #9)                           */}
      {/* ---------------------------------------------------------------- */}
      <footer className="mt-10 space-y-2">
        <DisclosureBundle
          disclosure={data.disclosure}
          notAdvice={data.not_advice}
        />
        {/* Standing <Disclaimer/> is now rendered by MaybeShell. */}
      </footer>
    </MaybeShell>
  );
}
