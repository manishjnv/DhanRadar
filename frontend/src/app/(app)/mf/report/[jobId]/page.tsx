'use client';

/**
 * MF Report page — DhanRadar launch-wedge.
 *
 * Compliance: user money figures (invested, current_value, return_pct, XIRR) are
 * shown because they are the user's OWN data, not proprietary DhanRadar scores.
 * DhanRadar label + confidence_band are rendered without any numeric score.
 * NOT_ADVICE disclaimer is prominently rendered.
 */

import * as React from 'react';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { LabelChip } from '@/components/ui/LabelChip';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { AllocationDonut } from '@/components/charts/AllocationDonut';
import { useCasStatus, useMfReport } from '@/features/mf/api';
import { cn } from '@/lib/cn';
import type { MfScheme, OverlapPair } from '@/features/mf/types';

// ---------------------------------------------------------------------------
// Progress view
// ---------------------------------------------------------------------------
function ProgressView({ progress }: { progress: number }) {
  return (
    <div className="mx-auto max-w-md py-16 text-center flex flex-col items-center gap-6">
      <div className="text-4xl" aria-hidden="true">📊</div>
      <div className="w-full">
        <ProgressBar value={progress} />
        <p className="mt-3 text-small text-ink-secondary">
          Analysing your portfolio… ~60 seconds
        </p>
      </div>
      <p className="text-caption text-ink-muted">
        We are reading your holdings, computing educational labels, and checking
        category allocation. No advisory recommendation is generated.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Summary row
// ---------------------------------------------------------------------------
function SummaryRow({
  totalInvested,
  currentValue,
  xirrPct,
  asOf,
  schemeCount,
}: {
  totalInvested: number;
  currentValue: number;
  xirrPct: number;
  asOf: string;
  schemeCount: number;
}) {
  const returnPct = ((currentValue - totalInvested) / totalInvested) * 100;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Card className="p-4">
        <p className="text-caption text-ink-muted uppercase tracking-wide">Total invested</p>
        <p className="mt-1 text-h3 font-medium text-ink tabular-nums">
          ₹{totalInvested.toLocaleString('en-IN')}
        </p>
      </Card>
      <Card className="p-4">
        <p className="text-caption text-ink-muted uppercase tracking-wide">Current value</p>
        <p className="mt-1 text-h3 font-medium text-ink tabular-nums">
          ₹{currentValue.toLocaleString('en-IN')}
        </p>
      </Card>
      <Card className="p-4">
        <p className="text-caption text-ink-muted uppercase tracking-wide">Returns</p>
        <p className={cn('mt-1 text-h3 font-medium tabular-nums', returnPct >= 0 ? 'text-emerald' : 'text-red')}>
          {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(1)}%
        </p>
      </Card>
      <Card className="p-4">
        <p className="text-caption text-ink-muted uppercase tracking-wide">XIRR</p>
        <p className={cn('mt-1 text-h3 font-medium tabular-nums', xirrPct >= 0 ? 'text-emerald' : 'text-red')}>
          {xirrPct >= 0 ? '+' : ''}{xirrPct.toFixed(1)}%
        </p>
        <p className="text-caption text-ink-muted">{schemeCount} schemes · as of {asOf}</p>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Schemes table
// ---------------------------------------------------------------------------
function SchemesTable({ schemes }: { schemes: MfScheme[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <thead>
          <tr className="border-b border-line text-caption text-ink-muted">
            <th className="pb-2 text-left font-medium">Fund</th>
            <th className="pb-2 text-left font-medium hidden sm:table-cell">Category</th>
            <th className="pb-2 text-right font-medium hidden md:table-cell">Invested</th>
            <th className="pb-2 text-right font-medium">Current</th>
            <th className="pb-2 text-right font-medium">Return</th>
            <th className="pb-2 text-left font-medium pl-4">Assessment</th>
          </tr>
        </thead>
        <tbody>
          {schemes.map((s) => (
            <tr key={s.isin} className="border-b border-line last:border-0">
              <td className="py-2.5 pr-3">
                <p className="font-medium text-ink leading-snug">{s.scheme_name}</p>
                <p className="text-caption text-ink-muted">{s.amc_name}</p>
              </td>
              <td className="py-2.5 pr-3 text-ink-secondary hidden sm:table-cell">{s.category}</td>
              <td className="py-2.5 pr-3 text-right text-ink-secondary tabular-nums hidden md:table-cell">
                ₹{s.invested.toLocaleString('en-IN')}
              </td>
              <td className="py-2.5 pr-3 text-right text-ink tabular-nums">
                ₹{s.current_value.toLocaleString('en-IN')}
              </td>
              <td className={cn('py-2.5 pr-3 text-right tabular-nums font-medium', s.return_pct >= 0 ? 'text-emerald' : 'text-red')}>
                {s.return_pct >= 0 ? '+' : ''}{s.return_pct.toFixed(1)}%
              </td>
              <td className="py-2.5 pl-4">
                <LabelChip label={s.label} confidenceBand={s.confidence_band} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overlap section
// ---------------------------------------------------------------------------
function OverlapSection({ pairs }: { pairs: OverlapPair[] }) {
  if (pairs.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Portfolio Overlap</CardTitle>
      </CardHeader>
      <CardBody>
        <p className="text-small text-ink-secondary mb-4">
          High overlap between funds may reduce diversification benefit.
        </p>
        <ul className="flex flex-col gap-3">
          {pairs.map((p, i) => (
            <li key={i} className="flex items-center gap-3 text-small">
              <span className="flex-1 text-ink">{p.fund_a}</span>
              <span className="text-ink-muted shrink-0">↔</span>
              <span className="flex-1 text-ink">{p.fund_b}</span>
              <span
                className={cn(
                  'shrink-0 font-medium tabular-nums',
                  p.overlap_pct > 40 ? 'text-amber' : 'text-ink-secondary',
                )}
              >
                {p.overlap_pct}%
              </span>
            </li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Report view
// ---------------------------------------------------------------------------
function ReportView({ jobId }: { jobId: string }) {
  const { data, isLoading, isError, refetch } = useMfReport(jobId, true);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 rounded-lg" />)}
        </div>
        <Skeleton className="h-48 rounded-lg" />
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <ErrorCard
        title="Could not load report"
        message="Your analysis may still be processing. Try refreshing in a moment."
        onRetry={() => refetch()}
      />
    );
  }

  const { summary, schemes, category_allocation, overlap, disclosure, not_advice } = data;

  return (
    <div className="flex flex-col gap-6">
      <SummaryRow
        totalInvested={summary.total_invested}
        currentValue={summary.current_value}
        xirrPct={summary.xirr_pct}
        asOf={summary.as_of}
        schemeCount={summary.scheme_count}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Category Allocation</CardTitle>
          </CardHeader>
          <CardBody>
            <AllocationDonut data={category_allocation} />
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Your Holdings</CardTitle>
          </CardHeader>
          <CardBody>
            <SchemesTable schemes={schemes} />
          </CardBody>
        </Card>
      </div>

      <OverlapSection pairs={overlap} />

      {/* Contextual #9 disclosure — version-tied disclosure + not_advice from
          the backend, rendered on the labelled-holdings surface. The standing
          site-wide line is the AppShell footer, not here. */}
      {(disclosure || not_advice) && (
        <div className="rounded-lg border border-line bg-surface-2 p-4">
          <DisclosureBundle disclosure={disclosure} notAdvice={not_advice} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function ReportPage({ params }: { params: { jobId: string } }) {
  const { jobId } = params;
  const { data: statusData } = useCasStatus(jobId);
  const isDone = statusData?.status === 'done';
  const isError = statusData?.status === 'error';

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-h2 font-medium text-ink">Portfolio Report</h1>
        <p className="mt-1 text-small text-ink-secondary">
          Educational analysis of your mutual fund holdings
        </p>
      </div>

      {isError ? (
        <div className="rounded-lg border p-6">
          <h2 className="text-base font-medium text-ink">
            We couldn&rsquo;t process this statement
          </h2>
          <p className="mt-2 text-small text-ink-secondary">
            The upload failed — the CAS PDF may be password-protected, not a CAS
            statement, or corrupted. Nothing was saved.
          </p>
          <a
            href="/mf/upload"
            className="mt-4 inline-block text-small font-medium text-ink underline"
          >
            Upload again &rarr;
          </a>
        </div>
      ) : !isDone ? (
        <ProgressView progress={statusData?.progress_pct ?? 0} />
      ) : (
        <ReportView jobId={jobId} />
      )}
    </div>
  );
}
