'use client';

/**
 * Fund Detail page — /mf/fund/[isin]
 *
 * Public educational view of a single mutual fund's rank, label, and returns.
 * Data is resolved from the SEBI category list (uses `category` URL param set
 * by FundExplorerTable row navigation). No auth required.
 *
 * Compliance: non-neg #1 (no advisory verbs), #2 (no numeric score), #9 (NOT_ADVICE).
 */

import * as React from 'react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { Card, CardBody } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { LabelChip } from '@/components/ui/LabelChip';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { useFundDetail } from '@/features/mf/api';
import { cn } from '@/lib/cn';
import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function FundDetailSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <Skeleton className="h-5 w-40 rounded-full" />
      <div>
        <Skeleton className="h-4 w-48 rounded mb-2" />
        <Skeleton className="h-8 w-3/4 rounded mb-2" />
        <Skeleton className="h-4 w-1/3 rounded" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-28 rounded-xl" />
      </div>
      <div>
        <Skeleton className="h-4 w-24 rounded mb-3" />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
        </div>
      </div>
      <Skeleton className="h-20 rounded-lg" />
      <Skeleton className="h-16 rounded-lg" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// 404 / not-found state
// ---------------------------------------------------------------------------

function FundNotFound({ backHref }: { backHref: string }) {
  return (
    <div className="flex flex-col gap-6">
      <Link
        href={backHref}
        className="inline-flex items-center gap-1 text-small text-ink-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded transition-colors w-fit"
      >
        ← Back to Fund Explorer
      </Link>
      <div className="rounded-xl border border-line bg-surface-2 p-10 text-center">
        <p className="text-small font-medium text-ink">Fund not found</p>
        <p className="mt-1 text-caption text-ink-muted">
          This fund isn&apos;t in our database yet, or browse from the Fund Explorer to find it.
        </p>
        <Link
          href="/mf/explore"
          className="mt-4 inline-block text-small font-medium text-royal hover:text-royal/80 underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded transition-colors"
        >
          Go to Fund Explorer →
        </Link>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Return value card — colored with +/- prefix, mobile-readable
// ---------------------------------------------------------------------------

function ReturnCard({ label, pct }: { label: string; pct: number | null }) {
  return (
    <Card className="p-4">
      <p className="text-caption text-ink-muted uppercase tracking-wide">{label}</p>
      {pct != null ? (
        <p className={cn(
          'mt-1 text-h3 font-medium tabular-nums font-mono',
          pct >= 0 ? 'text-emerald' : 'text-red',
        )}>
          {pct >= 0 ? '+' : ''}{pct.toFixed(1)}%
        </p>
      ) : (
        <p className="mt-1 text-h3 font-medium text-ink-muted font-mono">—</p>
      )}
      <p className="mt-0.5 text-caption text-ink-faint">annualised, trailing</p>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Plan / option chip — same style as FundExplorerTable
// ---------------------------------------------------------------------------

function PlanChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center px-2 py-px rounded bg-surface-3 border border-line font-mono text-caption font-semibold uppercase tracking-wide text-ink-secondary">
      {children}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Main detail view (client — needs hooks)
// ---------------------------------------------------------------------------

function FundDetailView() {
  const params = useParams<{ isin: string }>();
  const searchParams = useSearchParams();

  const isin = params.isin;
  const category = searchParams.get('category');

  const { data: fund, isLoading } = useFundDetail(isin, category);

  const backHref = category
    ? `/mf/explore?category=${encodeURIComponent(category)}`
    : '/mf/explore';

  // No category provided — can't resolve fund without it
  if (!category) {
    return <FundNotFound backHref={backHref} />;
  }

  if (isLoading) {
    return <FundDetailSkeleton />;
  }

  if (!fund) {
    return <FundNotFound backHref={backHref} />;
  }

  const optionLabel =
    fund.option_type === 'growth'            ? 'Growth'
    : fund.option_type === 'idcw'            ? 'IDCW'
    : fund.option_type === 'dividend_reinvest' ? 'Div Reinvest'
    : fund.option_type === 'dividend_payout'   ? 'Div Payout'
    : null;

  return (
    <div className="flex flex-col gap-6">

      {/* Back navigation — same pattern as report page */}
      <Link
        href={backHref}
        className="inline-flex items-center gap-1 text-small text-ink-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded transition-colors w-fit"
      >
        ← Back to Fund Explorer
      </Link>

      {/* Fund header */}
      <div>
        <p className="font-mono text-caption uppercase tracking-[0.08em] font-semibold text-royal mb-1">
          {fund.sebi_category}
        </p>
        <h1 className="text-h2 font-medium text-ink">{fund.scheme_name}</h1>
        {fund.amc_name && (
          <p className="mt-1 text-small text-ink-secondary">{fund.amc_name}</p>
        )}
      </div>

      {/* Assessment + Rank — 2-col on sm+, single col on mobile */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">

        {/* Assessment card */}
        <Card className="p-4">
          <p className="text-caption text-ink-muted uppercase tracking-wide mb-2">Assessment</p>
          <LabelChip
            label={fund.verb_label as Label}
            confidenceBand={(fund.confidence_band ?? undefined) as ConfidenceBand | undefined}
          />
          {/* Plan + option type chips — same styling as FundExplorerTable */}
          {(fund.plan_type || optionLabel) && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {fund.plan_type && (
                <PlanChip>{fund.plan_type === 'direct' ? 'Direct' : 'Regular'}</PlanChip>
              )}
              {optionLabel && <PlanChip>{optionLabel}</PlanChip>}
            </div>
          )}
        </Card>

        {/* Rank card */}
        <Card className="p-4">
          <p className="text-caption text-ink-muted uppercase tracking-wide mb-2">Rank in Category</p>
          <p className="text-h2 font-medium text-ink font-mono tabular-nums">
            #{fund.category_rank}
            <span className="text-h3 text-ink-muted"> of {fund.category_total}</span>
          </p>
          <p className="mt-1 text-caption text-ink-muted">
            Market-wide rank — educational signal only
          </p>
        </Card>
      </div>

      {/* Returns comparison — 2-col grid, never overflows on mobile */}
      <div>
        <p className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted mb-3">
          Returns (category comparison)
        </p>
        <div className="grid grid-cols-2 gap-4">
          <ReturnCard label="1Y Return" pct={fund.return_1y_pct} />
          <ReturnCard label="3Y Return" pct={fund.return_3y_pct} />
        </div>
        <p className="mt-2 text-caption text-ink-faint">
          Past returns do not indicate future performance. For educational comparison only.
        </p>
      </div>

      {/* AMC AUM — only when populated (ADR-0035: AMC-level only) */}
      {fund.amc_level_aum_crore != null && (
        <Card className="p-4">
          <p className="text-caption text-ink-muted uppercase tracking-wide">AMC Assets Under Management</p>
          <p className="mt-1 text-h3 font-medium text-ink font-mono tabular-nums">
            ₹{fund.amc_level_aum_crore.toLocaleString('en-IN', { maximumFractionDigits: 0 })} Cr
          </p>
          <p className="mt-0.5 text-caption text-ink-muted">AMC-level AUM (scheme-level not yet sourced)</p>
        </Card>
      )}

      {/* Upload CAS CTA */}
      <div className="rounded-lg border border-line bg-surface-2 p-4">
        <p className="text-small font-medium text-ink">See this fund in your portfolio</p>
        <p className="mt-1 text-caption text-ink-muted">
          Upload your Consolidated Account Statement to see performance in your personal portfolio context.
        </p>
        <Link
          href="/mf/upload"
          className="mt-3 inline-flex items-center gap-1 text-small font-medium text-royal hover:text-royal/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded underline underline-offset-2 transition-colors"
        >
          Upload CAS →
        </Link>
      </div>

      {/* NOT_ADVICE disclosure — non-neg #9, fail-closed hard-coded fallback */}
      <div className="rounded-lg border border-line bg-surface-2 p-4">
        <DisclosureBundle
          notAdvice="For education only — not investment advice. Rankings and assessments are educational signals derived from factual data, not recommendations to buy, sell, or hold any fund."
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page export
// ---------------------------------------------------------------------------

export default function FundDetailPage() {
  return (
    <div className="flex flex-col gap-6">
      <FundDetailView />
    </div>
  );
}
