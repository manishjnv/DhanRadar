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
import { FadeUp } from '@/components/ui/FadeUp';
import { useCountUp } from '@/features/mf/useCountUp';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { LabelChip } from '@/components/ui/LabelChip';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { WhyThisLabelPanel } from '@/components/mf/WhyThisLabelPanel';
import { PortfolioCommentaryCard } from '@/components/mf/PortfolioCommentaryCard';
import { ResearchAssistant } from '@/components/mf/ResearchAssistant';
import { ConcentrationCallout } from '@/components/mf/ConcentrationCallout';
import { StickyPortfolioBar } from '@/components/mf/StickyPortfolioBar';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { AllocationDonut } from '@/components/charts/AllocationDonut';
import { PortfolioHealthSummary } from '@/components/mf/PortfolioHealthSummary';
import { useCasStatus, useMfReport, useMfLabelHistory } from '@/features/mf/api';
import type { LabelHistoryEntry } from '@/features/mf/types';
import { cn } from '@/lib/cn';
import type { Label } from '@/components/charts/ScoreRing';
import type { MfScheme, OverlapPair } from '@/features/mf/types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Format a UTC ISO-8601 string to a readable IST datetime, e.g. "11 Jun 2026, 8:41 AM".
 * Returns "—" when the input is absent or unparseable.
 */
const IST_FORMAT = new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'Asia/Kolkata',
});

function formatIstDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  // isNaN check: invalid ISO strings produce an invalid Date whose getTime() is NaN.
  if (isNaN(d.getTime())) return '—';
  return IST_FORMAT.format(d);
}

// ---------------------------------------------------------------------------
// Progress view
// ---------------------------------------------------------------------------
const PROGRESS_TIPS = [
  'Reading fund categories…',
  'Computing educational labels…',
  'Checking category allocation…',
  'Analysing portfolio composition…',
  'Preparing your report…',
];

function ProgressView({ progress }: { progress: number }) {
  const [tipIdx, setTipIdx] = React.useState(0);
  React.useEffect(() => {
    const id = setInterval(() => setTipIdx((i) => (i + 1) % PROGRESS_TIPS.length), 8000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="mx-auto max-w-md py-16 text-center flex flex-col items-center gap-6">
      <svg
        width="64" height="64" viewBox="0 0 64 64"
        aria-hidden="true"
        className="animate-spin"
        style={{ animationDuration: '1.8s', animationTimingFunction: 'linear' }}
      >
        <circle cx="32" cy="32" r="26" fill="none" stroke="var(--border)" strokeWidth="5" />
        <circle
          cx="32" cy="32" r="26" fill="none"
          stroke="var(--dr-royal)" strokeWidth="5" strokeLinecap="round"
          strokeDasharray="35 128"
        />
      </svg>
      <div className="w-full">
        <ProgressBar value={progress} />
        <p className="mt-3 text-small text-ink-secondary">{PROGRESS_TIPS[tipIdx]}</p>
      </div>
      <p className="text-caption text-ink-muted">
        No advisory recommendation is generated. ~60 seconds.
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
  const animInvested = useCountUp(totalInvested);
  const animCurrent  = useCountUp(currentValue);
  const returnPct    = ((animCurrent - animInvested) / totalInvested) * 100;
  const animXirr     = useCountUp(xirrPct);
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Card className="p-4">
        <p className="text-caption text-ink-muted uppercase tracking-wide">Total invested</p>
        <p className="mt-1 text-h3 font-medium text-ink tabular-nums">
          ₹{animInvested.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
        </p>
      </Card>
      <Card className="p-4">
        <p className="text-caption text-ink-muted uppercase tracking-wide">Current value</p>
        <p className="mt-1 text-h3 font-medium text-ink tabular-nums">
          ₹{animCurrent.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
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
        <p className={cn('mt-1 text-h3 font-medium tabular-nums', animXirr >= 0 ? 'text-emerald' : 'text-red')}>
          {animXirr >= 0 ? '+' : ''}{animXirr.toFixed(1)}%
        </p>
        <p className="text-caption text-ink-muted">{schemeCount} schemes · as of {formatIstDateTime(asOf)}</p>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Feature 3 — label change delta helpers
// ---------------------------------------------------------------------------

const LABEL_RANK: Record<Label, number> = {
  in_form: 4,
  on_track: 3,
  off_track: 2,
  out_of_form: 1,
  insufficient_data: 0,
};

function DeltaBadge({ current, previous }: { current: Label; previous: Label | null }) {
  if (!previous || previous === current) return null;
  const improved = LABEL_RANK[current] > LABEL_RANK[previous];
  const label = `Was ${previous.replace(/_/g, '-')} in previous upload`;
  return (
    <span
      title={label}
      aria-label={label}
      className={cn(
        'shrink-0 text-base font-bold leading-none select-none',
        improved ? 'text-emerald' : 'text-red',
      )}
    >
      {improved ? '↑' : '↓'}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Schemes table
// ---------------------------------------------------------------------------
function SchemesTable({
  schemes,
  historyByIsin,
  historyLocked,
}: {
  schemes: MfScheme[];
  historyByIsin: Record<string, LabelHistoryEntry[]>;
  historyLocked: boolean;
}) {
  // F1-A: per-fund "Why this label" disclosure. Track which funds are expanded.
  const [expanded, setExpanded] = React.useState<Set<string>>(() => new Set());

  const toggle = (isin: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(isin)) next.delete(isin);
      else next.add(isin);
      return next;
    });

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
          {schemes.map((s) => {
            const isOpen = expanded.has(s.isin);
            const panelId = `why-${s.isin}`;
            return (
              <React.Fragment key={s.isin}>
                <tr className="border-b border-line last:border-0">
                  <td className="py-2.5 pr-3">
                    <p className="font-medium text-ink leading-snug">{s.scheme_name}</p>
                    <p className="text-caption text-ink-muted">{s.amc_name}</p>
                  </td>
                  <td className="py-2.5 pr-3 text-ink-secondary hidden sm:table-cell">{s.category}</td>
                  <td className="py-2.5 pr-3 text-right text-ink-secondary tabular-nums hidden md:table-cell">
                    {s.invested == null ? '—' : `₹${s.invested.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`}
                  </td>
                  <td className="py-2.5 pr-3 text-right text-ink tabular-nums">
                    ₹{s.current_value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                  </td>
                  <td className={cn('py-2.5 pr-3 text-right tabular-nums font-medium', s.return_pct >= 0 ? 'text-emerald' : 'text-red')}>
                    {s.return_pct >= 0 ? '+' : ''}{s.return_pct.toFixed(1)}%
                  </td>
                  <td className="py-2.5 pl-4">
                    <div className="flex items-center gap-2">
                      <LabelChip label={s.label} confidenceBand={s.confidence_band} />
                      {/* Feature 3: label change delta (↑/↓) */}
                      <DeltaBadge current={s.label} previous={s.previous_label} />
                      {/* Feature 5: market-wide category rank — ordinal only, never score */}
                      {s.category_rank != null && s.category_total != null && (
                        <span className="text-caption text-ink-muted whitespace-nowrap">
                          #{s.category_rank} of {s.category_total}
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={() => toggle(s.isin)}
                        aria-expanded={isOpen}
                        aria-controls={panelId}
                        className="shrink-0 min-h-[44px] inline-flex items-center text-caption px-2 py-0.5 rounded-full bg-surface-2 text-ink-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 transition-colors"
                      >
                        {isOpen ? 'Hide' : 'Why?'}
                      </button>
                    </div>
                  </td>
                </tr>
                <tr>
                  <td colSpan={6} className="p-0">
                    <div
                      className={cn(
                        'grid transition-all duration-200 ease-in-out',
                        isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
                      )}
                    >
                      <div className="overflow-hidden">
                        <div className="pb-3">
                          <WhyThisLabelPanel
                            id={panelId}
                            contributingSignals={s.contributing_signals}
                            contradictingSignals={s.contradicting_signals}
                            confidenceFactors={s.confidence_factors ?? null}
                            historyEntries={historyByIsin[s.isin] ?? []}
                            historyLocked={historyLocked}
                          />
                        </div>
                      </div>
                    </div>
                  </td>
                </tr>
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overlap section
// ---------------------------------------------------------------------------
function OverlapSection({ pairs }: { pairs: OverlapPair[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Portfolio Overlap</CardTitle>
      </CardHeader>
      <CardBody>
        <p className="text-small text-ink-secondary mb-4">
          When two funds hold many of the same stocks, buying both adds less
          diversification than it appears. A 60% overlap means 60% of that money
          effectively sits in a shared pool — not two separate baskets.
        </p>
        {pairs.length === 0 ? (
          <div className="rounded-lg border border-line bg-surface-2 p-4 text-center">
            <p className="text-small font-medium text-ink">
              Stock-level overlap analysis coming soon
            </p>
            <p className="mt-1 text-caption text-ink-muted">
              Overlap requires each fund&apos;s individual stock holdings. We are
              building this feed from SEBI-mandated monthly portfolio disclosures.
            </p>
          </div>
        ) : (
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
        )}
      </CardBody>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Report view
// ---------------------------------------------------------------------------
function ReportView({ jobId }: { jobId: string }) {
  const { data, isLoading, isError, refetch } = useMfReport(jobId, true);
  const [activeFilter, setActiveFilter] = React.useState<Label | null>(null);

  // B4: track whether the SummaryRow is visible in the viewport.
  const summaryRef = React.useRef<HTMLDivElement>(null);
  const [summaryVisible, setSummaryVisible] = React.useState(true);
  // Depend on `data` so the observer is (re)attached after the loading skeleton
  // resolves — summaryRef.current is null during the loading phase.
  React.useEffect(() => {
    const el = summaryRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(([entry]) => setSummaryVisible(entry.isIntersecting), {
      threshold: 0,
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, [data]);

  // Feature 2: fetch label history (Plus-gated); enabled once portfolio_id is known.
  const { entries: historyEntries, isLocked: historyLocked } = useMfLabelHistory(
    data?.portfolio_id ?? null,
  );

  // Group history entries by ISIN for O(1) lookup in SchemesTable / WhyThisLabelPanel.
  const historyByIsin = React.useMemo<Record<string, LabelHistoryEntry[]>>(() => {
    const map: Record<string, LabelHistoryEntry[]> = {};
    for (const e of historyEntries) {
      (map[e.isin] ??= []).push(e);
    }
    return map;
  }, [historyEntries]);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        {/* 4 KPI cards */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 rounded-lg" />)}
        </div>
        {/* Commentary card */}
        <Skeleton className="h-24 rounded-lg" />
        {/* Health summary chip row */}
        <div className="flex gap-2">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-8 w-24 rounded-full" />)}
        </div>
        {/* Main grid: donut + table rows */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Skeleton className="h-64 rounded-lg lg:col-span-1" />
          <div className="lg:col-span-2 flex flex-col gap-2">
            {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}
          </div>
        </div>
        {/* Overlap card */}
        <Skeleton className="h-32 rounded-lg" />
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

  const { summary, schemes, category_allocation, overlap, commentary, disclosure, not_advice } =
    data;

  const filteredSchemes = activeFilter
    ? schemes.filter((s) => s.label === activeFilter)
    : schemes;

  return (
    <div className="flex flex-col gap-6">
      {/* B4: sticky bar — slides in when SummaryRow scrolls out of view */}
      <StickyPortfolioBar
        currentValue={summary.current_value}
        schemes={schemes}
        visible={!summaryVisible}
      />

      <div ref={summaryRef}>
        <FadeUp delay={0}>
          <SummaryRow
            totalInvested={summary.total_invested}
            currentValue={summary.current_value}
            xirrPct={summary.xirr_pct}
            asOf={summary.as_of}
            schemeCount={summary.scheme_count}
          />
        </FadeUp>
      </div>

      {/* F1-B: plain-language AI portfolio summary (governed gateway, consent-gated).
          Hides itself when the backend returns no commentary. */}
      <FadeUp delay={80}>
        <PortfolioCommentaryCard commentary={commentary} />
      </FadeUp>

      {/* F1: Portfolio health summary — label counts as filter chips.
          Counts are always from the full schemes list; filter applies only to the table. */}
      <FadeUp delay={160}>
        <PortfolioHealthSummary
          schemes={schemes}
          activeFilter={activeFilter}
          onFilterChange={setActiveFilter}
        />
      </FadeUp>

      <FadeUp delay={240}>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-1">
            <CardHeader>
              <CardTitle>Category Allocation</CardTitle>
            </CardHeader>
            <CardBody>
              <AllocationDonut data={category_allocation} />
              {/* D1: factual concentration callout — top-3 categories, no advisory framing */}
              <ConcentrationCallout allocation={category_allocation} />
            </CardBody>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader className="flex items-center justify-between gap-2">
              <CardTitle>Your Holdings</CardTitle>
              <a
                href="/mf/explore"
                className="text-caption text-ink-muted hover:text-ink underline underline-offset-2 shrink-0"
              >
                Compare with full market &rarr;
              </a>
            </CardHeader>
            <CardBody>
              {/* Feature 3: historyByIsin powers ↑/↓ delta; Feature 2: history shown in WhyPanel */}
              <SchemesTable
                schemes={filteredSchemes}
                historyByIsin={historyByIsin}
                historyLocked={historyLocked}
              />
            </CardBody>
          </Card>
        </div>
      </FadeUp>

      <FadeUp delay={320}>
        <OverlapSection pairs={overlap} />
      </FadeUp>

      {/* F2: Plus-gated grounded research assistant (non-advisory, consent-gated,
          daily-capped). 402 → upgrade prompt rendered by the component itself. */}
      <FadeUp delay={360}>
        <ResearchAssistant jobId={jobId} />
      </FadeUp>

      {/* Contextual #9 disclosure — version-tied disclosure + not_advice from
          the backend, rendered on the labelled-holdings surface (which now also
          carries the per-fund "Why this label" panels). Rendered UNCONDITIONALLY
          with a hard-coded NOT_ADVICE fallback so an empty backend string can
          never silently drop the disclosure from a label surface (non-neg #9,
          fail-closed). The standing site-wide line is the AppShell footer. */}
      <FadeUp delay={440}>
        <div className="rounded-lg border border-line bg-surface-2 p-4">
          <DisclosureBundle
            disclosure={disclosure || undefined}
            notAdvice={not_advice || 'For education only — not investment advice.'}
          />
        </div>
      </FadeUp>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function ReportPage({ params }: { params: { jobId: string } }) {
  const { jobId } = params;
  const { data: statusData, timedOut } = useCasStatus(jobId);
  const isDone = statusData?.status === 'done';
  const isFailed = statusData?.status === 'error';

  // Show an error card whenever the job explicitly failed OR the client-side
  // timeout fired (job is stuck and still not terminal after 150 s).
  const showError = isFailed || timedOut;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-h2 font-medium text-ink">Portfolio Report</h1>
        <p className="mt-1 text-small text-ink-secondary">
          Educational analysis of your mutual fund holdings
        </p>
      </div>

      {showError ? (
        <div className="rounded-lg border p-6">
          <h2 className="text-base font-medium text-ink">
            {timedOut
              ? 'This is taking longer than expected'
              : "We couldn't process this statement"}
          </h2>
          <p className="mt-2 text-small text-ink-secondary">
            {timedOut
              ? 'Processing is taking longer than usual. Please try uploading your statement again.'
              : "The upload failed - the CAS PDF may be password-protected, not a CAS statement, or corrupted. Nothing was saved."}
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
