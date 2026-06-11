/**
 * ConceptArticle — presentational detail view for one concept explainer (C1).
 *
 * Pure server-safe presentational component (no hooks, no fetch) so it is
 * directly unit-testable in vitest/jsdom; the async Server Component page
 * fetches and passes `concept`. Markdown body rendered server-side via
 * react-markdown (no client JS for parsing) with the same element mapping as
 * the G8 tax article page.
 *
 * Compliance (#9): contextual DisclosureBundle sits ABOVE the body; the
 * standing <Disclaimer/> is provided by MaybeShell at page level.
 */
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import type { ConceptDetail } from '@/features/learn/concepts-api';
import { ChevronLeft } from 'lucide-react';

export function ConceptArticle({ concept }: { concept: ConceptDetail }) {
  return (
    <>
      {/* Back link */}
      <Link
        href="/learn/concepts"
        className="inline-flex items-center gap-1 text-small text-ink-secondary hover:text-ink transition-colors mb-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded"
      >
        <ChevronLeft size={14} aria-hidden="true" />
        Investing Basics
      </Link>

      <article>
        <header className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-caption text-ink-muted uppercase tracking-wide">
              {concept.category}
            </span>
          </div>
          <h1 className="text-h2 font-medium text-ink">{concept.title}</h1>
          <p className="text-body text-ink-secondary mt-2">{concept.summary}</p>
        </header>

        {/* ---------------------------------------------------------------- */}
        {/* Contextual disclosure — sits right above body (non-negotiable #9) */}
        {/* ---------------------------------------------------------------- */}
        <DisclosureBundle
          disclosure={concept.disclosure}
          notAdvice={concept.not_advice}
          className="mb-6"
        />

        {/* ---------------------------------------------------------------- */}
        {/* Markdown body — rendered server-side via react-markdown           */}
        {/* ---------------------------------------------------------------- */}
        <div className="prose-dr text-body text-ink space-y-4">
          <ReactMarkdown
            components={{
              h1: ({ children }) => (
                <h2 className="text-h2 font-medium text-ink mt-6 mb-2">{children}</h2>
              ),
              h2: ({ children }) => (
                <h2 className="text-h2 font-medium text-ink mt-6 mb-2">{children}</h2>
              ),
              h3: ({ children }) => (
                <h3 className="text-h3 font-medium text-ink mt-4 mb-1">{children}</h3>
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
            {concept.body_md}
          </ReactMarkdown>
        </div>

        {/* Article footer */}
        <footer className="mt-8 pt-6 border-t border-line space-y-2">
          <p className="text-caption text-ink-muted">
            Last updated: {concept.updated_at}
          </p>
          {/* Standing <Disclaimer/> is rendered by MaybeShell. */}
        </footer>
      </article>
    </>
  );
}
