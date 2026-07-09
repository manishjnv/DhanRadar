'use client';

/**
 * Admin Analytics — /admin/analytics
 * Tier-A read-only page (Admin.md §14 Analytics).
 *
 * Sections:
 *   A — KPI StatCards (signups total/30d · CAS uploads total/30d · portfolios · reports · conversions)
 *   B — Conversion funnel (CAS uploaded → portfolio created → report generated + conversion_rate_pct)
 *
 * Four-state contract: skeleton / empty / error+retry / data.
 * No advisory verbs. Simple labeled bars — no chart lib dependency.
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { useAdminAnalyticsOverview } from '@/features/admin/api';
import { formatRelative } from '@/components/admin/utils';

// ---------------------------------------------------------------------------
// Static class map for grid — Tailwind JIT cannot see interpolated names
// ---------------------------------------------------------------------------
const GRID_COLS_3 = 'grid-cols-3';
const GRID_COLS_4 = 'grid-cols-4';

// ---------------------------------------------------------------------------
// Skeletons
// ---------------------------------------------------------------------------
function StatRowSkeleton({ cols }: { cols: number }) {
  const lg = cols === 4 ? GRID_COLS_4 : GRID_COLS_3;
  return (
    <div className={`grid grid-cols-2 gap-3 sm:${lg}`}>
      {[...Array(cols)].map((_, i) => (
        <Skeleton key={i} className="h-24 rounded-xl" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Funnel bar — simple labeled percentage bar, no chart lib
// ---------------------------------------------------------------------------
function FunnelBar({
  label,
  value,
  max,
  isLast = false,
}: {
  label: string;
  value: number;
  max: number;
  isLast?: boolean;
}) {
  const pct = max > 0 ? Math.min(Math.round((value / max) * 100), 100) : 0;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-3">
        <span className="text-small text-ink-secondary">{label}</span>
        <span className="font-mono text-small tabular-nums text-ink font-medium">
          {value.toLocaleString('en-IN')}
        </span>
      </div>
      <div className="h-3 rounded-full bg-surface-2 overflow-hidden">
        <div
          className="h-full rounded-full bg-royal/70"
          style={{ width: `${pct}%` }}
          aria-label={`${label}: ${value} (${pct}%)`}
        />
      </div>
      {!isLast && (
        <div className="flex justify-center">
          <span className="text-ink-faint text-caption">↓</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Analytics page
// ---------------------------------------------------------------------------
export default function AdminAnalyticsPage() {
  const analyticsQ = useAdminAnalyticsOverview();

  return (
    <div className="flex flex-col gap-8">
      {/* Page header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-h2 font-medium text-ink">Analytics</h1>
          <p className="mt-1 text-small text-ink-muted">
            Product analytics: activation funnel · CAS-upload→report conversion · usage.
            Infra/host metrics are in Grafana.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {analyticsQ.dataUpdatedAt > 0 && (
            <span className="text-caption text-ink-muted">
              Last updated {formatRelative(new Date(analyticsQ.dataUpdatedAt).toISOString())}
            </span>
          )}
          <Button variant="ghost" size="sm" onClick={() => analyticsQ.refetch()}>
            <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Section A — KPI StatCards */}
      <section aria-labelledby="section-analytics-kpi">
        <h2 id="section-analytics-kpi" className="mb-3 text-h3 font-medium text-ink">
          Key Metrics
        </h2>
        {analyticsQ.isLoading && <StatRowSkeleton cols={4} />}
        {analyticsQ.isError && (
          <ErrorCard
            title="Could not load analytics"
            onRetry={() => analyticsQ.refetch()}
            className="max-w-md"
          />
        )}
        {analyticsQ.data && (() => {
          const d = analyticsQ.data;
          const n = (v: number) => v.toLocaleString('en-IN');
          const tiles: Array<{ title: string; value: string; sub: string }> = [
            {
              title: 'Signups',
              value: n(d.signups_total),
              sub: `${n(d.signups_30d)} in the last 30 days`,
            },
            {
              title: 'Statement Uploads',
              value: n(d.cas_uploads_total),
              sub: `${n(d.cas_uploads_30d)} in 30 days · includes failed`,
            },
            {
              title: 'Portfolios',
              value: n(d.portfolios_created),
              sub: 'Created from uploads',
            },
            {
              title: 'Reports',
              value: n(d.reports_generated),
              sub: 'Approximate — one per portfolio refresh',
            },
            {
              title: 'Paid Plans',
              value: n(d.premium_conversions),
              sub: 'All non-free records ever, incl. cancelled',
            },
          ];
          return (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {tiles.map((t) => (
                <div key={t.title} className="rounded-lg border border-line bg-surface p-3">
                  <p className="text-caption uppercase tracking-wide text-ink-muted">{t.title}</p>
                  <p className="mt-1 font-mono text-h3 font-medium tabular-nums text-ink">{t.value}</p>
                  <p className="mt-0.5 text-caption text-ink-muted leading-snug">{t.sub}</p>
                </div>
              ))}
            </div>
          );
        })()}
      </section>

      {/* Section B — Conversion funnel */}
      <section aria-labelledby="section-funnel">
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <CardTitle id="section-funnel">Activation Funnel</CardTitle>
                  <span className="text-caption text-ink-muted font-normal">All time</span>
                </div>
                <p className="mt-1 text-small text-ink-muted">
                  CAS uploaded → portfolio created → report generated
                </p>
              </div>
              {analyticsQ.data && (
                <div
                  className="shrink-0 text-right"
                  title="Conversion rate = reports generated ÷ CAS uploads, expressed as a percentage."
                >
                  <span className="font-mono text-h2 font-medium tabular-nums text-ink">
                    {analyticsQ.data.conversion_rate_pct.toFixed(1)}%
                  </span>
                  <p className="text-caption text-ink-muted">conversion rate</p>
                </div>
              )}
            </div>
          </CardHeader>
          <CardBody>
            {analyticsQ.isLoading && (
              <div className="flex flex-col gap-4">
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} className="h-12 rounded-md" />
                ))}
              </div>
            )}
            {analyticsQ.isError && (
              <ErrorCard title="Could not load funnel" onRetry={() => analyticsQ.refetch()} />
            )}
            {analyticsQ.data && (() => {
              const { funnel } = analyticsQ.data;
              const max = funnel.cas_uploaded || 1;
              const steps: Array<{ label: string; value: number }> = [
                { label: 'CAS Uploaded',      value: funnel.cas_uploaded },
                { label: 'Portfolio Created',  value: funnel.portfolio_created },
                { label: 'Report Generated',   value: funnel.report_generated },
              ];
              if (funnel.cas_uploaded === 0 && funnel.portfolio_created === 0 && funnel.report_generated === 0) {
                return (
                  <EmptyState
                    title="No funnel data yet"
                    description="Funnel metrics will appear once users start uploading CAS files."
                    className="py-8"
                  />
                );
              }
              return (
                <div className="max-w-lg flex flex-col gap-4">
                  {steps.map((step, i) => (
                    <FunnelBar
                      key={step.label}
                      label={step.label}
                      value={step.value}
                      max={max}
                      isLast={i === steps.length - 1}
                    />
                  ))}
                </div>
              );
            })()}
          </CardBody>
        </Card>
      </section>
    </div>
  );
}
