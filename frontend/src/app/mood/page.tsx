'use client';

/**
 * /mood — PUBLIC Market Mood page (no auth, no AppShell sidebar).
 *
 * Compliance checklist (self-verified):
 *  #1  Educational read only — no advisory verbs (buy/sell/hold/caution/avoid).
 *  #2  No numeric score or percentage rendered against mood.
 *  #4  No Authorization header added (apiClient enforces).
 *  #5  Auth = cookie-only; this public page simply has no auth guard at all.
 *  #9  disclosure + not_advice strings from API rendered; <Disclaimer/> present.
 *
 * Route: top-level app/mood/ (NOT inside (app) group) → no AuthGuard, no sidebar.
 */

import * as React from 'react';
import Link from 'next/link';
import { Button }     from '@/components/ui/Button';
import { Card, CardBody } from '@/components/ui/Card';
import { Skeleton }   from '@/components/ui/Skeleton';
import { ErrorCard }  from '@/components/ui/ErrorCard';
import { EmptyState } from '@/components/ui/EmptyState';
import { Disclaimer } from '@/components/ui/Disclaimer';
import { Compass } from 'lucide-react';
import { MoodGauge, REGIME_COLOR, REGIME_DISPLAY } from '@/components/mood/MoodGauge';
import { useMoodCurrent, useMoodHistory } from '@/features/mood/api';
import { ApiError } from '@/lib/apiClient';
import type { Regime } from '@/features/mood/types';

// ---------------------------------------------------------------------------
// History strip — 30 small colored squares, one per day
// ---------------------------------------------------------------------------
function HistoryStrip({ days }: { days: number }) {
  const { data, isError } = useMoodHistory(days);

  if (isError || !data || data.length === 0) return null;

  return (
    <section aria-label="30-day regime history">
      <p className="text-caption text-ink-muted mb-2">Last {days} days</p>
      <div className="flex flex-wrap gap-1" role="list">
        {data.map((item) => (
          <div
            key={item.snapshot_date}
            role="listitem"
            title={`${item.snapshot_date}: ${REGIME_DISPLAY[item.regime as Regime]}`}
            className="h-3 w-3 rounded-sm"
            style={{ backgroundColor: REGIME_COLOR[item.regime as Regime] ?? '#6B7280' }}
            aria-label={`${item.snapshot_date}: ${REGIME_DISPLAY[item.regime as Regime]}`}
          />
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Factor lists — contributing / contradicting
// Uses neutral "+" / "−" markers — NOT green-up/red-down arrows that imply buy/sell
// ---------------------------------------------------------------------------
function FactorList({
  heading,
  items,
  marker,
}: {
  heading: string;
  items: string[];
  marker: '+' | '−';
}) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-small font-medium text-ink mb-1">{heading}</p>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item} className="flex items-start gap-1.5 text-small text-ink">
            <span className="text-ink-muted select-none" aria-hidden="true">
              {marker}
            </span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function MoodPage() {
  const { data, isLoading, isError, error, refetch } = useMoodCurrent();

  const is404 =
    isError && error instanceof ApiError && error.problem.status === 404;

  return (
    <div className="min-h-screen bg-bg">
      {/* ------------------------------------------------------------------ */}
      {/* Top bar — public shell (no AppShell sidebar)                        */}
      {/* ------------------------------------------------------------------ */}
      <header className="bg-surface border-b border-line px-4 py-3 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5">
          {/* Decorative mark; wordmark text provides the accessible name. */}
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
          <h1 className="text-h2 font-medium text-ink">Market Mood</h1>
          <p className="text-small text-ink-secondary mt-1">
            An educational read of market sentiment, updated twice daily. Not investment advice.
          </p>
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Loading state                                                      */}
        {/* ---------------------------------------------------------------- */}
        {isLoading && (
          <Card>
            <CardBody>
              <div className="flex flex-col items-center gap-4 py-4">
                <Skeleton className="h-[120px] w-[200px] rounded-lg" />
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-4 w-64" />
              </div>
            </CardBody>
          </Card>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* 404 — snapshot not yet computed                                   */}
        {/* ---------------------------------------------------------------- */}
        {is404 && (
          <EmptyState
            icon={<Compass size={28} aria-hidden="true" />}
            title="Market mood is being computed"
            description="Check back shortly — the next read publishes at 9:00 AM and 4:00 PM IST."
          />
        )}

        {/* ---------------------------------------------------------------- */}
        {/* Other error                                                        */}
        {/* ---------------------------------------------------------------- */}
        {isError && !is404 && (
          <ErrorCard
            message="Could not load market mood. Please try again."
            onRetry={() => void refetch()}
          />
        )}

        {/* ---------------------------------------------------------------- */}
        {/* Success — render mood card                                         */}
        {/* ---------------------------------------------------------------- */}
        {data && (
          <div className="space-y-6">
            {/* Primary mood card */}
            <Card>
              <CardBody>
                {/* Gauge — centered, regime label + band only, no numeric */}
                <div className="flex justify-center py-2">
                  <MoodGauge
                    regime={data.regime as Regime}
                    confidenceBand={data.confidence_band}
                  />
                </div>

                {/* Commentary — only shown when data_quality ok and present */}
                <div className="mt-4">
                  {data.data_quality === 'ok' && data.commentary ? (
                    <p className="text-body text-ink">{data.commentary}</p>
                  ) : (
                    <p className="text-small text-ink-muted">
                      Commentary is unavailable for this read.
                    </p>
                  )}
                </div>

                {/* What's driving this */}
                {(data.contributing_factors.length > 0 ||
                  data.contradicting_factors.length > 0) && (
                  <div className="mt-6 border-t border-line pt-4">
                    <p className="text-small font-semibold text-ink mb-3">
                      What&rsquo;s driving this
                    </p>
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <FactorList
                        heading="Supporting"
                        items={data.contributing_factors}
                        marker="+"
                      />
                      <FactorList
                        heading="Counterweights"
                        items={data.contradicting_factors}
                        marker="−"
                      />
                    </div>
                  </div>
                )}
              </CardBody>
            </Card>

            {/* 30-day history strip */}
            <HistoryStrip days={30} />

            {/* ------------------------------------------------------------ */}
            {/* Footer — snapshot date, disclosure (non-negotiable #9)        */}
            {/* ------------------------------------------------------------ */}
            <footer className="space-y-2">
              <p className="text-caption text-ink-muted">
                As of {data.snapshot_date}
              </p>
              {/* disclosure and not_advice from API MUST be rendered (#9) */}
              <p className="text-caption text-ink-muted">{data.disclosure}</p>
              <p className="text-caption text-ink-muted">{data.not_advice}</p>
              <Disclaimer />
            </footer>
          </div>
        )}
      </main>
    </div>
  );
}
