'use client';

/**
 * Dashboard page — DhanRadar launch wedge.
 *
 * Compliance: educational labels only, no advisory verbs, no numeric DhanRadar
 * score in DOM, confidence as band word only, NOT_ADVICE disclaimer in footer.
 * Market index values and user money figures ARE allowed per architecture rules.
 */

import * as React from 'react';
import Link from 'next/link';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { LabelChip } from '@/components/ui/LabelChip';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import {
  useIndices,
  useTopScored,
  useMarketNews,
  usePortfolioSummary,
} from '@/features/dashboard/api';
import { ApiError } from '@/lib/apiClient';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// IndexKPI card
// ---------------------------------------------------------------------------
function IndexKPICard({
  name,
  value,
  changePct,
}: {
  name: string;
  value: number;
  changePct: number;
}) {
  const positive = changePct >= 0;
  return (
    <Card className="flex flex-col gap-1 p-4">
      <span className="text-caption text-ink-muted uppercase tracking-wide">{name}</span>
      <span className="text-h3 font-medium text-ink tabular-nums">
        {value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
      </span>
      <span
        className={cn(
          'text-small font-medium tabular-nums',
          positive ? 'text-emerald' : 'text-red',
        )}
      >
        {positive ? '+' : ''}{changePct.toFixed(2)}%
      </span>
    </Card>
  );
}

function IndexKPIRow() {
  const { data, isLoading, isError, refetch } = useIndices();

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-20 rounded-lg" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <ErrorCard
        title="Could not load market indices"
        onRetry={() => refetch()}
        className="h-20"
      />
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {data?.map((idx) => (
        <IndexKPICard
          key={idx.name}
          name={idx.name}
          value={idx.value}
          changePct={idx.change_pct}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TopScored table
// ---------------------------------------------------------------------------
function TopScoredTable() {
  const { data, isLoading, isError, refetch } = useTopScored();

  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 rounded" />)}
      </div>
    );
  }

  if (isError) {
    return <ErrorCard title="Could not load top funds" onRetry={() => refetch()} />;
  }

  const funds = data?.funds ?? [];

  return (
    <div className="flex flex-col gap-3">
      {funds.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-small">
            <thead>
              <tr className="border-b border-line text-caption text-ink-muted">
                <th className="pb-2 text-left font-medium">Fund</th>
                <th className="pb-2 text-left font-medium">Category</th>
                <th className="pb-2 text-left font-medium">Assessment</th>
              </tr>
            </thead>
            <tbody>
              {funds.map((fund) => (
                <tr key={fund.isin} className="border-b border-line last:border-0">
                  <td className="py-2.5 pr-4 text-ink font-medium">{fund.scheme_name}</td>
                  <td className="py-2.5 pr-4 text-ink-secondary">{fund.category}</td>
                  <td className="py-2.5">
                    <LabelChip label={fund.label} confidenceBand={fund.confidence_band} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {/* Disclosure bundle — required adjacent to any label/AI surface (non-negotiable #9) */}
      {data && (
        <DisclosureBundle
          disclosure={data.disclosure}
          notAdvice={data.not_advice}
          className="mt-1"
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// News list
// ---------------------------------------------------------------------------
function NewsList() {
  const { data, isLoading, isError, refetch } = useMarketNews();

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-12 rounded" />)}
      </div>
    );
  }

  if (isError) {
    return <ErrorCard title="Could not load news" onRetry={() => refetch()} />;
  }

  return (
    <ul className="flex flex-col gap-3">
      {data?.map((item) => (
        <li key={item.id} className="flex flex-col gap-0.5 border-b border-line pb-3 last:border-0 last:pb-0">
          <span className="text-small text-ink leading-snug">{item.title}</span>
          <span className="text-caption text-ink-muted">
            {item.source} · {item.freshness}
          </span>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Portfolio snapshot / cold-start card
// ---------------------------------------------------------------------------
function PortfolioSnapshot() {
  const { data, isLoading, isError, error } = usePortfolioSummary();

  const isColdStart =
    isError && error instanceof ApiError && error.problem.status === 404;

  if (isLoading) {
    return <Skeleton className="h-28 rounded-lg" />;
  }

  if (isColdStart || (!isLoading && !data)) {
    // Cold-start onboarding card
    return (
      <Card className="flex flex-col items-start gap-4 p-6 sm:flex-row sm:items-center">
        <div className="flex-1">
          <p className="text-h3 font-medium text-ink">Get started in 60 seconds</p>
          <p className="mt-1 text-small text-ink-secondary">
            Upload your Consolidated Account Statement (CAS) and get a fully labelled
            educational analysis of your mutual fund portfolio.
          </p>
        </div>
        <Button asChild size="md">
          <Link href="/mf/upload">Upload your CAS → 60s report</Link>
        </Button>
      </Card>
    );
  }

  if (isError) {
    return <ErrorCard title="Portfolio summary unavailable" />;
  }

  // Has portfolio
  const summary = data!;
  return (
    <Card className="flex flex-col gap-4 p-6">
      {/* KPI row */}
      <div className="flex flex-wrap items-center gap-6 sm:gap-10">
        <div>
          <p className="text-caption text-ink-muted uppercase tracking-wide">Current value</p>
          <p className="text-h2 font-medium text-ink tabular-nums">
            {summary.current_value != null
              ? `₹${summary.current_value.toLocaleString('en-IN')}`
              : '—'}
          </p>
        </div>
        <div>
          <p className="text-caption text-ink-muted uppercase tracking-wide">XIRR</p>
          <p
            className={cn(
              'text-h3 font-medium tabular-nums',
              summary.xirr_pct == null
                ? 'text-ink-muted'
                : summary.xirr_pct >= 0
                  ? 'text-emerald'
                  : 'text-red',
            )}
          >
            {summary.xirr_pct != null
              ? `${summary.xirr_pct >= 0 ? '+' : ''}${summary.xirr_pct.toFixed(1)}%`
              : '—'}
          </p>
        </div>
        <div>
          <p className="text-caption text-ink-muted uppercase tracking-wide">Funds</p>
          <p className="text-h3 font-medium text-ink tabular-nums">{summary.fund_count}</p>
        </div>
        <div className="sm:ml-auto">
          <Button variant="outline" size="sm" asChild>
            <Link href="/mf/upload">View full report</Link>
          </Button>
        </div>
      </div>

      {/* Per-fund label list */}
      {summary.funds.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-small">
            <thead>
              <tr className="border-b border-line text-caption text-ink-muted">
                <th className="pb-2 text-left font-medium">Fund</th>
                <th className="pb-2 text-left font-medium">Assessment</th>
              </tr>
            </thead>
            <tbody>
              {summary.funds.map((fund) => (
                <tr key={fund.isin} className="border-b border-line last:border-0">
                  <td className="py-2 pr-4 text-ink">{fund.scheme_name}</td>
                  <td className="py-2">
                    <LabelChip label={fund.label} confidenceBand={fund.confidence_band} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Disclosure bundle — required adjacent to any label/AI surface (non-negotiable #9) */}
      <DisclosureBundle
        disclosure={summary.disclosure}
        notAdvice={summary.not_advice}
        className="mt-1"
      />
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-h2 font-medium text-ink">Dashboard</h1>
        <p className="mt-1 text-small text-ink-secondary">
          Indian market overview
        </p>
      </div>

      {/* Row 1 — Market indices */}
      <IndexKPIRow />

      {/* Row 2 — Top scored + News */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Top-Assessed Funds</CardTitle>
          </CardHeader>
          <CardBody>
            <TopScoredTable />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Market News</CardTitle>
          </CardHeader>
          <CardBody>
            <NewsList />
          </CardBody>
        </Card>
      </div>

      {/* Portfolio snapshot. Standing disclaimer is the AppShell footer. */}
      <PortfolioSnapshot />
    </div>
  );
}
