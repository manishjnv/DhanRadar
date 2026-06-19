'use client';

/**
 * AI Quality / Eval -- /admin/ai/eval
 * Phase 4, Tier-B read-only (Admin.md §15, §18 step 4).
 *
 * Backend: AiEvalResponse (aiops_schemas.py)
 *   - quality_issues: QualityIssueRow[] (metric_key/label/current_value/threshold/unit/status)
 *   - groundedness: InstrumentedFalse (instrumented:false + note)
 *
 * Sections:
 *   A -- Quality issues table (typed shape from aiops_schemas)
 *   B -- Groundedness eval: not yet instrumented note
 *
 * Four-state contract. No advisory verbs.
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { RefreshCw, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { HealthBadge, type BadgeStatus } from '@/components/admin/HealthBadge';
import {
  useAdminAIEval,
  type AdminAIQualityIssueRow,
} from '@/features/admin/api';

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
// Quality issues table -- typed QualityIssueRow shape
// ---------------------------------------------------------------------------
const QI_HEADERS = ['Metric', 'Label', 'Value', 'Threshold', 'Unit', 'Status'];

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
      <table className="w-full text-small">
        <thead>
          <tr className="border-b border-line">
            {QI_HEADERS.map((h) => (
              <th
                key={h}
                className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {issues.map((row) => (
            <tr
              key={row.metric_key}
              className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors"
            >
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">{row.metric_key}</td>
              <td className="py-2.5 pr-4 text-[11px] text-ink">{row.label}</td>
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
          ))}
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
            <h1 className="text-h2 font-medium text-ink">Quality / Eval</h1>
            <p className="mt-1 text-small text-ink-muted">
              Quality issue tracking and groundedness evaluation results.
              Sourced from{' '}
              <code className="font-mono text-caption">mf.data_quality_issues</code>{' '}
              and{' '}
              <code className="font-mono text-caption">ai_recommendation_audit</code>.
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

        {/* Section B -- Groundedness note */}
        {q.data && (
          <section aria-labelledby="section-ai-eval-groundedness">
            <div className="rounded-lg border border-line bg-surface p-5">
              <h2
                id="section-ai-eval-groundedness"
                className="text-h3 font-medium text-ink mb-2"
              >
                Groundedness Evaluation
              </h2>
              <div className="flex items-center gap-2 mb-3">
                <HealthBadge
                  status={q.data.groundedness.instrumented ? 'Healthy' : 'Planned'}
                />
                <span className="text-small text-ink-muted">
                  {q.data.groundedness.instrumented
                    ? 'Groundedness eval instrumented'
                    : 'Not yet instrumented'}
                </span>
              </div>
              <p className="text-small text-ink-muted">
                {q.data.groundedness.note ||
                  'Groundedness evaluation -- automated scoring of whether AI outputs are supported by source material -- is not yet instrumented. This will be added as part of the Phase 5 eval harness.'}
              </p>
            </div>
          </section>
        )}
      </div>
    </>
  );
}
