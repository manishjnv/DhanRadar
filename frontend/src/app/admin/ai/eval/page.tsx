'use client';

/**
 * AI Quality & Eval -- /admin/ai/eval
 * Phase 4, Tier-B read-only (Admin.md §15, §18 step 4).
 *
 * Backend: AiEvalResponse (aiops_schemas.py)
 *   - quality_issues: QualityIssueRow[] (metric_key/label/current_value/threshold/unit/status)
 *   - groundedness: InstrumentedFalse (instrumented:false + note)
 *
 * Sections:
 *   A -- Quality issues table (typed shape from aiops_schemas)
 *   B -- AI Output Accuracy Check: not yet available note
 *
 * Four-state contract. No advisory verbs.
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { RefreshCw, CheckCircle2, Info } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { HealthBadge, type BadgeStatus } from '@/components/admin/HealthBadge';
import { formatRelative } from '@/components/admin/utils';
import {
  useAdminAIEval,
  type AdminAIQualityIssueRow,
} from '@/features/admin/api';

// ---------------------------------------------------------------------------
// Metric help text — what each threshold means operationally
// ---------------------------------------------------------------------------
const METRIC_HELP: Record<string, string> = {
  missing_nav: 'Funds without a NAV entry for today. Above threshold means reports may show stale prices.',
  stale_nav: 'Funds whose latest NAV is older than 2 business days. Affects scoring freshness.',
  missing_metrics: 'Funds with no computed metrics (returns, volatility). These are excluded from rankings.',
  unscored_funds: 'Active funds that have not been scored in the current cycle. Above threshold blocks the ranking job.',
  low_corpus: 'Funds with fewer than 12 months of NAV history — too little data for reliable signals.',
};

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------
function ContentSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {[...Array(3)].map((_, i) => (
        <Skeleton key={i} className="h-10 rounded-md" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Quality issues table -- raw metric_key moved to tooltip; human label shown
// ---------------------------------------------------------------------------
const QI_HEADERS = ['Label', 'Value', 'Threshold', 'Unit', 'Status'];

function statusToBadge(s: string): BadgeStatus {
  if (s === 'ok') return 'ok';
  if (s === 'warning') return 'warning';
  if (s === 'critical') return 'critical';
  return 'Planned';
}

function QualityIssueTable({ issues }: { issues: AdminAIQualityIssueRow[] }) {
  if (issues.length === 0) {
    return (
      <EmptyState
        icon={<CheckCircle2 size={28} />}
        title="No quality issues recorded"
        description="Quality issue entries will appear here once warning or critical thresholds are breached."
        className="py-8"
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small" aria-label="Data quality issues" role="table">
        <caption className="sr-only">
          Data quality metrics — warning and critical threshold breaches from the MF data pipeline.
          Values are refreshed each time the quality monitor runs.
        </caption>
        <thead>
          <tr className="border-b border-line">
            {QI_HEADERS.map((h) => (
              <th
                key={h}
                scope="col"
                className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {issues.map((row) => {
            const help = METRIC_HELP[row.metric_key];
            const snoozeUntil = (row as { acknowledged_until?: string | null }).acknowledged_until;
            const isSnoozed = snoozeUntil != null && new Date(snoozeUntil) > new Date();
            return (
              <tr
                key={row.metric_key}
                className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors"
              >
                <td className="py-2.5 pr-4 text-[11px] text-ink">
                  <span className="flex items-start gap-1.5">
                    <span>
                      <span className="font-medium">{row.label}</span>
                      {isSnoozed && (
                        <span className="ml-2 text-[10px] text-ink-muted">
                          Snoozed until {formatRelative(snoozeUntil!)}
                        </span>
                      )}
                    </span>
                    {help && (
                      <span
                        title={help}
                        className="mt-px shrink-0 cursor-help text-ink-muted"
                        aria-label={`Help: ${help}`}
                      >
                        <Info size={11} />
                      </span>
                    )}
                  </span>
                </td>
                <td className="py-2.5 pr-4 font-mono text-[11px] tabular-nums text-right text-ink">
                  {row.current_value != null ? row.current_value : '--'}
                </td>
                <td className="py-2.5 pr-4 font-mono text-[11px] tabular-nums text-right text-ink-muted">
                  {row.threshold != null ? row.threshold : '--'}
                </td>
                <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">{row.unit}</td>
                <td className="py-2.5">
                  <HealthBadge status={statusToBadge(row.status)} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function AdminAIEvalPage() {
  const q = useAdminAIEval();

  return (
    <>
      <div className="flex flex-col gap-8">
        {/* Page header */}
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-h2 font-medium text-ink">Data Quality &amp; AI Evaluation</h1>
            <p className="mt-1 text-small text-ink-muted">
              Quality issue tracking and AI output accuracy results.
              Sourced from the MF data pipeline and the AI output log.
              {q.dataUpdatedAt ? (
                <> Last updated {formatRelative(new Date(q.dataUpdatedAt).toISOString())}.</>
              ) : null}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => q.refetch()}>
            <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
            Refresh
          </Button>
        </div>

        {/* Section A -- Quality issues */}
        <section aria-labelledby="section-ai-eval-quality">
          <Card>
            <CardHeader>
              <CardTitle id="section-ai-eval-quality">Quality Issues</CardTitle>
              <p className="mt-1 text-small text-ink-muted">
                Warning and critical threshold breaches from the MF data quality monitor.
                Each metric has a threshold — values above it indicate a problem that may
                affect reports or scores shown to users.
              </p>
            </CardHeader>
            <CardBody>
              {q.isLoading && <ContentSkeleton />}
              {q.isError && (
                <ErrorCard title="Could not load eval data" onRetry={() => q.refetch()} />
              )}
              {q.data && <QualityIssueTable issues={q.data.quality_issues} />}
            </CardBody>
          </Card>
        </section>

        {/* Section B -- AI Output Accuracy Check */}
        {q.data && (
          <section aria-labelledby="section-ai-eval-groundedness">
            <div className="rounded-lg border border-line bg-surface p-5">
              <h2
                id="section-ai-eval-groundedness"
                className="text-h3 font-medium text-ink mb-2"
              >
                AI Output Accuracy Check
              </h2>
              <div className="flex items-center gap-2 mb-3">
                <HealthBadge
                  status={q.data.groundedness.instrumented ? 'Healthy' : 'Planned'}
                />
                <span className="text-small text-ink-muted">
                  {q.data.groundedness.instrumented
                    ? 'AI output accuracy check is active'
                    : 'Not yet available'}
                </span>
              </div>
              {q.data.groundedness.instrumented && q.data.groundedness.value !== null ? (
                <p className="text-small text-ink-muted">
                  Average groundedness{' '}
                  <span className="font-mono text-ink">
                    {(q.data.groundedness.value * 100).toFixed(0)}%
                  </span>{' '}
                  across {q.data.groundedness.sample_count.toLocaleString('en-IN')} sampled
                  AI outputs over the last {q.data.groundedness.window_days} days
                  {q.data.groundedness.low_flags > 0
                    ? ` · ${q.data.groundedness.low_flags.toLocaleString('en-IN')} flagged low`
                    : ''}
                  . A sampled grader scores how well each AI output is supported by its
                  source data.
                </p>
              ) : (
                <p className="text-small text-ink-muted">
                  {q.data.groundedness.note ||
                    'Automated checking that AI-generated outputs are supported by underlying fund data is not yet available.'}
                </p>
              )}
            </div>
          </section>
        )}
      </div>
    </>
  );
}
