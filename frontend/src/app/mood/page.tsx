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
 * Chrome (header + standing Disclaimer) provided by MaybeShell.
 */

import * as React from 'react';
import { Card, CardBody } from '@/components/ui/Card';
import { Skeleton }   from '@/components/ui/Skeleton';
import { ErrorCard }  from '@/components/ui/ErrorCard';
import { EmptyState } from '@/components/ui/EmptyState';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { Compass } from 'lucide-react';
import { MoodGauge } from '@/components/mood/MoodGauge';
import { DriverFactorList } from '@/components/mood/DriverFactorList';
import { MoodMovement } from '@/components/mood/MoodMovement';
import { MoodTimeline } from '@/components/mood/MoodTimeline';
import { MoodPeriods } from '@/components/mood/MoodPeriods';
import { ConfidenceExplanation } from '@/components/mood/ConfidenceExplanation';
import { useMoodCurrent, useMoodHistory } from '@/features/mood/api';
import { ApiError } from '@/lib/apiClient';
import type { Regime } from '@/features/mood/types';
import { relativeTime } from '@/features/mood/relative-time';

// The 30-day history is now shown by the MoodPeriods (monthly/weekly/daily) strip.
// Factor lists are rendered by the shared DriverFactorList (numberless tier bars).

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function MoodPage() {
  const { data, isLoading, isError, error, refetch } = useMoodCurrent();
  // days=2 → today + the prior snapshot, for the "vs yesterday" hero line.
  const { data: recent } = useMoodHistory(2);

  // "Yesterday" = the most recent snapshot whose date differs from today's.
  // History is ordered snapshot_date.desc(), so the first non-today row is it.
  const yesterdayRegime: Regime | null = React.useMemo(() => {
    if (!data || !recent) return null;
    const prior = recent.find((h) => h.snapshot_date !== data.snapshot_date);
    return prior ? prior.regime : null;
  }, [data, recent]);

  const is404 =
    isError && error instanceof ApiError && error.problem.status === 404;

  // The endpoint can return 200 with data_quality "unavailable" (regime
  // "data_unavailable") when no snapshot has been computed yet. Treat that the
  // same as a 404 "being computed" — rendering the gauge for it is meaningless.
  const unavailable =
    !!data &&
    (data.data_quality === 'unavailable' || data.regime === 'data_unavailable');

  return (
    <MaybeShell>
      {/* Page heading */}
      <div className="mb-6">
        <h1 className="text-h2 text-ink">Market Mood</h1>
        <p className="text-small text-ink-secondary mt-1">
          An educational read of market sentiment, updated twice daily.
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
      {(is404 || unavailable) && (
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
      {data && !unavailable && (
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

              {/* How sentiment moved vs yesterday — labels + trend word only. */}
              <div className="mt-2 flex justify-center text-center">
                <MoodMovement
                  todayRegime={data.regime as Regime}
                  yesterdayRegime={yesterdayRegime}
                  trend={data.trend}
                />
              </div>

              {/* Plain-language WHY behind the confidence band — words only, no
                  counts/percent/score (non-neg #2); data reliability only (#1). */}
              <div className="mt-2 flex justify-center">
                <ConfidenceExplanation
                  dataQuality={data.data_quality}
                  confidenceBand={data.confidence_band}
                  className="max-w-prose text-center"
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
                  <p className="text-small font-medium text-ink mb-1">
                    What&rsquo;s driving this
                  </p>
                  <p className="text-caption text-ink-muted mb-3">
                    A longer bar means the factor is moving the mood more.
                    Supporting factors pull toward today&rsquo;s reading; counterweights pull the other way.
                  </p>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <DriverFactorList
                      heading="Supporting"
                      items={data.contributing_factors}
                      marker="+"
                    />
                    <DriverFactorList
                      heading="Counterweights"
                      items={data.contradicting_factors}
                      marker="−"
                    />
                  </div>
                </div>
              )}
            </CardBody>
          </Card>

          {/* How the mood label moved over time — labels only, no scores/returns. */}
          <MoodTimeline todayRegime={data.regime as Regime} todayDate={data.snapshot_date} />

          {/* Monthly / weekly / daily mood markers */}
          <MoodPeriods />

          {/* ------------------------------------------------------------ */}
          {/* Footer — snapshot date, disclosure (non-negotiable #9)        */}
          {/* ------------------------------------------------------------ */}
          <footer className="space-y-2">
            <p
              className="font-mono text-caption tabular-nums text-ink-muted"
              title={data.snapshot_at ?? data.snapshot_date}
            >
              {data.snapshot_at
                ? `updated ${relativeTime(data.snapshot_at)}`
                : `As of ${data.snapshot_date}`}
            </p>
            {/* Contextual #9 disclosure from API (next to the mood read). */}
            <DisclosureBundle
              disclosure={data.disclosure}
              notAdvice={data.not_advice}
            />
            {/* Standing <Disclaimer/> is now rendered by MaybeShell. */}
          </footer>
        </div>
      )}
    </MaybeShell>
  );
}
