/**
 * /learn/tax/[slug] — Single tax article page.
 *
 * Server Component (async); NOT inside (app) route group → no AuthGuard.
 * Chrome (header + standing Disclaimer) provided by MaybeShell.
 *
 * SEO acquisition asset: per-article metadata via generateMetadata.
 * Renders Markdown body_md with react-markdown (server-rendered, no JS shipped
 * to client for parsing). Returns Next.js notFound() on 404 from the API.
 * Compliance (#9): contextual DisclosureBundle + standing <Disclaimer/>.
 */
import type { Metadata } from 'next';
import { notFound }        from 'next/navigation';
import Link                from 'next/link';
import ReactMarkdown       from 'react-markdown';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { fetchTaxArticle } from '@/features/learn/api';
import { ChevronLeft }     from 'lucide-react';

// Render per-request (SSR), never statically prerendered at build — the page
// fetches the backend, which is not reachable during `next build`. Still fully
// server-rendered HTML for crawlers (SEO intact).
export const dynamic = 'force-dynamic';

// ---------------------------------------------------------------------------
// Per-article SEO metadata
// ---------------------------------------------------------------------------
export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const article = await fetchTaxArticle(params.slug);
  if (!article) {
    return {
      title: 'Article not found — DhanRadar',
    };
  }
  return {
    title:       `${article.title} — DhanRadar Tax Education`,
    description: article.summary,
    openGraph: {
      title:       `${article.title} — DhanRadar Tax Education`,
      description: article.summary,
      type:        'article',
      siteName:    'DhanRadar',
    },
  };
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default async function TaxArticlePage({
  params,
}: {
  params: { slug: string };
}) {
  const article = await fetchTaxArticle(params.slug);
  if (!article) notFound();

  return (
    <MaybeShell>
      {/* Back link */}
      <Link
        href="/learn/tax"
        className="inline-flex items-center gap-1 text-small text-ink-secondary hover:text-ink transition-colors mb-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded"
      >
        <ChevronLeft size={14} aria-hidden="true" />
        Tax Education
      </Link>

      {/* Article header */}
      <article>
        <header className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <span className="font-mono text-caption text-ink-muted uppercase tracking-[0.06em]">
              {article.category}
            </span>
            <span className="text-caption text-ink-faint" aria-hidden="true">·</span>
            <span className="font-mono text-caption text-ink-muted tabular-nums">{article.fy_label}</span>
          </div>
          <h1 className="text-h2 text-ink">{article.title}</h1>
          <p className="text-body text-ink-secondary mt-2">{article.summary}</p>
        </header>

        {/* ---------------------------------------------------------------- */}
        {/* Contextual disclosure — sits right above body (non-negotiable #9) */}
        {/* ---------------------------------------------------------------- */}
        <DisclosureBundle
          disclosure={article.disclosure}
          notAdvice={article.not_advice}
          className="mb-6"
        />

        {/* ---------------------------------------------------------------- */}
        {/* Markdown body — rendered server-side via react-markdown           */}
        {/* ---------------------------------------------------------------- */}
        <div className="prose-dr text-body text-ink space-y-4">
          <ReactMarkdown
            components={{
              h1: ({ children }) => (
                <h2 className="text-h2 text-ink mt-6 mb-2">{children}</h2>
              ),
              h2: ({ children }) => (
                <h2 className="text-h2 text-ink mt-6 mb-2">{children}</h2>
              ),
              h3: ({ children }) => (
                <h3 className="text-h3 text-ink mt-4 mb-1">{children}</h3>
              ),
              p: ({ children }) => (
                <p className="text-body text-ink leading-relaxed">{children}</p>
              ),
              ul: ({ children }) => (
                <ul className="list-disc list-outside pl-5 space-y-1 text-body text-ink">
                  {children}
                </ul>
              ),
              ol: ({ children }) => (
                <ol className="list-decimal list-outside pl-5 space-y-1 text-body text-ink">
                  {children}
                </ol>
              ),
              li: ({ children }) => (
                <li className="text-body text-ink">{children}</li>
              ),
              strong: ({ children }) => (
                <strong className="font-semibold text-ink">{children}</strong>
              ),
              em: ({ children }) => (
                <em className="italic text-ink-secondary">{children}</em>
              ),
              blockquote: ({ children }) => (
                <blockquote className="border-l-4 border-line pl-4 text-ink-secondary italic">
                  {children}
                </blockquote>
              ),
              code: ({ children }) => (
                <code className="font-mono text-small bg-surface-2 px-1 py-0.5 rounded-sm text-ink">
                  {children}
                </code>
              ),
              a: ({ href, children }) => (
                <a
                  href={href}
                  className="text-royal underline underline-offset-2 hover:text-royal/80"
                  target={href?.startsWith('http') ? '_blank' : undefined}
                  rel={href?.startsWith('http') ? 'noopener noreferrer' : undefined}
                >
                  {children}
                </a>
              ),
            }}
          >
            {article.body_md}
          </ReactMarkdown>
        </div>

        {/* Article footer */}
        <footer className="mt-8 pt-6 border-t border-line space-y-2">
          {article.source_note && (
            <p className="text-caption text-ink-muted">{article.source_note}</p>
          )}
          <p className="text-caption text-ink-muted">
            Last updated: <span className="font-mono tabular-nums">{article.updated_at}</span>
          </p>
          {/* Standing <Disclaimer/> is now rendered by MaybeShell. */}
        </footer>
      </article>
    </MaybeShell>
  );
}
