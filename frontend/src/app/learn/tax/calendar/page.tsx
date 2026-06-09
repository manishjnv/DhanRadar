/**
 * /learn/tax/calendar — FY Tax Calendar page.
 *
 * Server Component (async); NOT inside (app) route group → no AuthGuard.
 * Own header + footer (mirrors app/mood/page.tsx chrome); no AppShell.
 *
 * SEO acquisition asset: static metadata, ISR 5 min.
 * Compliance (#9): DisclosureBundle from API payload + standing <Disclaimer/>.
 */
import type { Metadata }   from 'next';
import Link                from 'next/link';
import { Button }          from '@/components/ui/Button';
import { Card, CardBody }  from '@/components/ui/Card';
import { Disclaimer }      from '@/components/ui/Disclaimer';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { fetchTaxCalendar } from '@/features/learn/api';
import { ChevronLeft, CalendarDays } from 'lucide-react';

// Render per-request (SSR), never statically prerendered at build — the page
// fetches the backend, which is not reachable during `next build`. Still fully
// server-rendered HTML for crawlers (SEO intact).
export const dynamic = 'force-dynamic';

// ---------------------------------------------------------------------------
// Static SEO metadata
// ---------------------------------------------------------------------------
export const metadata: Metadata = {
  title: 'FY Tax Calendar & Key Deadlines — DhanRadar Tax Education',
  description:
    'Key income-tax dates for the current financial year: ITR filing deadlines, ELSS lock-in reminders, advance tax dates, and more. Educational content only.',
  openGraph: {
    title:       'FY Tax Calendar & Key Deadlines — DhanRadar Tax Education',
    description: 'Key income-tax dates for the current financial year.',
    type:        'website',
    siteName:    'DhanRadar',
  },
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default async function TaxCalendarPage() {
  const data = await fetchTaxCalendar();

  return (
    <div className="min-h-screen bg-bg">
      {/* ------------------------------------------------------------------ */}
      {/* Top bar — public shell                                               */}
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
        {/* Back link */}
        <Link
          href="/learn/tax"
          className="inline-flex items-center gap-1 text-small text-ink-secondary hover:text-ink transition-colors mb-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded"
        >
          <ChevronLeft size={14} aria-hidden="true" />
          Tax Education
        </Link>

        {/* Page heading */}
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-1">
            <CalendarDays size={20} className="text-royal" aria-hidden="true" />
            <h1 className="text-h2 font-medium text-ink">Tax Calendar</h1>
          </div>
          <p className="text-small text-ink-secondary">
            Key income-tax dates and deadlines for{' '}
            <span className="font-medium text-ink">{data.fy_label}</span>
            {' '}({data.fy_start} – {data.fy_end}).
          </p>
        </div>

        {/* Key dates list */}
        {data.key_dates.length === 0 ? (
          <Card>
            <CardBody>
              <p className="text-small text-ink-muted text-center py-4">
                Calendar dates are being updated. Check back shortly.
              </p>
            </CardBody>
          </Card>
        ) : (
          <div
            className="space-y-3"
            role="list"
            aria-label={`Tax calendar for ${data.fy_label}`}
          >
            {data.key_dates.map((entry, idx) => (
              <div key={`${entry.date}-${idx}`} role="listitem">
                <Card>
                  <CardBody className="py-3">
                    <div className="flex items-start gap-4">
                      {/* Date badge */}
                      <div
                        className="shrink-0 text-caption font-medium text-royal bg-royal/10 rounded-md px-2 py-1 tabular-nums min-w-[88px] text-center"
                        aria-label={`Date: ${entry.date}`}
                      >
                        {entry.date}
                      </div>
                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <p className="text-small font-medium text-ink">{entry.label}</p>
                        {entry.note && (
                          <p className="text-caption text-ink-muted mt-0.5">{entry.note}</p>
                        )}
                      </div>
                    </div>
                  </CardBody>
                </Card>
              </div>
            ))}
          </div>
        )}

        {/* ELSS note */}
        {data.elss_note && (
          <div className="mt-6 bg-surface-2 border border-line rounded-lg px-4 py-3">
            <p className="text-small font-medium text-ink mb-0.5">ELSS note</p>
            <p className="text-small text-ink-secondary">{data.elss_note}</p>
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
