/**
 * /learn/tax — Tax education index page.
 *
 * Server Component (async); NOT inside (app) route group → no AuthGuard.
 * Own header + footer (mirrors app/mood/page.tsx chrome); no AppShell.
 *
 * SEO acquisition asset: fully server-rendered, static metadata, ISR 5 min.
 * Compliance (#9): DisclosureBundle from API payload + standing <Disclaimer/>.
 */
import type { Metadata } from 'next';
import Link from 'next/link';
import { Button }          from '@/components/ui/Button';
import { Card, CardBody }  from '@/components/ui/Card';
import { Disclaimer }      from '@/components/ui/Disclaimer';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { fetchTaxArticles } from '@/features/learn/api';
import type { TaxArticleSummary } from '@/features/learn/api';
import { CalendarDays }    from 'lucide-react';

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
              <h2 className="text-h3 font-medium text-ink group-hover:text-royal transition-colors leading-snug">
                {article.title}
              </h2>
              <p className="text-small text-ink-secondary mt-1 line-clamp-2">
                {article.summary}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 mt-3">
            <span className="text-caption text-ink-muted uppercase tracking-wide">
              {article.category}
            </span>
            <span className="text-caption text-ink-faint" aria-hidden="true">·</span>
            <span className="text-caption text-ink-muted">{article.fy_label}</span>
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
    <div className="min-h-screen bg-bg">
      {/* ------------------------------------------------------------------ */}
      {/* Top bar — public shell (no AppShell sidebar)                        */}
      {/* ------------------------------------------------------------------ */}
      <header className="bg-surface border-b border-line px-4 py-3 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/brand/icon.svg" alt="" width={26} height={26} className="shrink-0" />
          <span className="text-h3 font-medium text-navy">DhanRadar</span>
        </Link>
        <Button variant="outline" size="sm" asChild>
          <Link href="/dashboard">Open app</Link>
        </Button>
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Main content                                                         */}
      {/* ------------------------------------------------------------------ */}
      <main className="mx-auto max-w-2xl px-4 py-8">
        {/* Page heading */}
        <div className="mb-6">
          <h1 className="text-h2 font-medium text-ink">Tax Education</h1>
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
          <Disclaimer />
        </footer>
      </main>
    </div>
  );
}
