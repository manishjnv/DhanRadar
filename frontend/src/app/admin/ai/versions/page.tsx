'use client';

/**
 * AI Score Versioning — /admin/ai/versions
 * Phase 4, Tier-C read-only (Admin.md §15, §18 step 4).
 *
 * Sections:
 *   A — Registry versions table (version · created_by · approved_by · two_person_ok · activated · activated_at)
 *   B — Muted "Backtest vs benchmark & drift — not yet instrumented" note
 *   Footer — Disabled "Promote version — Phase 5 (two-person gate B6)"
 *
 * Four-state contract. No advisory verbs.
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { HealthBadge } from '@/components/admin/HealthBadge';
import { formatDateTime, formatRelative } from '@/components/admin/utils';
import { displayLabel } from '@/lib/displayLabel';
import {
  useAdminAIVersions,
  type AdminAIRegistryVersion,
} from '@/features/admin/api';

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------
function TableSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {[...Array(4)].map((_, i) => (
        <Skeleton key={i} className="h-10 rounded-md" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Registry versions table
// ---------------------------------------------------------------------------
const VERSION_HEADERS = [
  'Version', 'Created by', 'Approved by', 'Approved by Two People', 'Backtest', 'Currently Live', 'Activated at', 'Created at',
];

function VersionsTable({ versions }: { versions: AdminAIRegistryVersion[] }) {
  if (versions.length === 0) {
    return (
      <EmptyState
        title="No registry versions"
        description="Score model registry entries will appear here once model versions are registered."
        className="py-8"
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <caption className="sr-only">Score model version history — one row per registered model version</caption>
        <thead>
          <tr className="border-b border-line">
            {VERSION_HEADERS.map((h) => (
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
          {versions.map((v) => (
            <tr
              key={v.model_version}
              className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors"
            >
              <td className="py-2.5 pr-4 font-mono text-[11px] font-medium text-ink whitespace-nowrap">
                {v.model_version}
              </td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                {v.created_by ? (
                  <span title={v.created_by}>
                    {v.created_by.length > 8 ? v.created_by.slice(0, 8) + '…' : v.created_by}
                  </span>
                ) : '—'}
              </td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                {v.approved_by ? (
                  <span title={v.approved_by}>
                    {v.approved_by.length > 8 ? v.approved_by.slice(0, 8) + '…' : v.approved_by}
                  </span>
                ) : '—'}
              </td>
              <td className="py-2.5 pr-4">
                <HealthBadge status={v.two_person_ok ? 'Success' : 'Warning'} />
              </td>
              <td className="py-2.5 pr-4">
                {v.backtest_passed === null ? (
                  <span className="font-mono text-[11px] text-ink-muted" title="Backtest gate not asserted for this version">
                    not asserted
                  </span>
                ) : (
                  <HealthBadge status={v.backtest_passed ? 'Success' : 'Warning'} />
                )}
              </td>
              <td className="py-2.5 pr-4">
                <HealthBadge status={v.activated ? 'Healthy' : 'Paused'} />
              </td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                {formatDateTime(v.activated_at)}
              </td>
              <td className="py-2.5 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                {formatDateTime(v.created_at)}
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
export default function AdminAIVersionsPage() {
  const q = useAdminAIVersions();

  return (
    <>
      <div className="flex flex-col gap-8">
        {/* Page header */}
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-h2 font-medium text-ink">Score Versioning</h1>
            <p className="mt-1 text-small text-ink-muted">
              Each version is a snapshot of the scoring rules used to label funds.
              Only one version can be live at a time — “Currently Live” shows which one users see.
              Switching versions requires sign-off from two people.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="ghost"
              disabled
              title="Promote (coming soon) — making a version live requires approval from two people and a separate human sign-off"
              className="opacity-40 cursor-not-allowed"
            >
              Promote (coming soon)
            </Button>
            <div className="flex flex-col items-end gap-1">
              <Button variant="ghost" size="sm" onClick={() => q.refetch()}>
                <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
                Refresh
              </Button>
              {q.dataUpdatedAt ? (
                <span className="text-[10px] text-ink-muted">
                  Last updated {formatRelative(new Date(q.dataUpdatedAt).toISOString())}
                </span>
              ) : null}
            </div>
          </div>
        </div>

        {/* Section A — Registry versions */}
        <section aria-labelledby="section-ai-versions">
          <Card>
            <CardHeader>
              <CardTitle id="section-ai-versions">Score Model History</CardTitle>
              <p className="mt-1 text-small text-ink-muted">
                All scoring rule versions, newest first.
                Only the “Currently Live” version produces labels users see.
              </p>
            </CardHeader>
            <CardBody>
              {q.isLoading && <TableSkeleton />}
              {q.isError && (
                <ErrorCard title="Could not load versions" onRetry={() => q.refetch()} />
              )}
              {q.data && <VersionsTable versions={q.data.versions} />}
            </CardBody>
          </Card>
        </section>

        {/* Section B — Methodology monitoring (backtest gate + label drift) */}
        {q.data && (
          <section aria-labelledby="section-ai-gaps" className="flex flex-col gap-3">
            <h2 id="section-ai-gaps" className="text-h3 font-medium text-ink">
              Methodology Monitoring
            </h2>
            <div className="flex flex-col gap-2">
              <div className="rounded-lg border border-line bg-surface p-4 text-small text-ink-muted">
                <div className="flex items-center gap-2 mb-1">
                  <p className="font-medium text-ink">Backtest gate</p>
                  <HealthBadge status={q.data.backtest.instrumented ? 'Healthy' : 'Planned'} />
                </div>
                <p>
                  The §8 backtest pass-gate outcome is recorded per version (see the
                  Backtest column above). {q.data.backtest.versions_with_backtest} of{' '}
                  {q.data.versions.length} shown versions have an asserted pass/fail.
                  DhanRadar records the activation-gate pass/fail, not a historical-accuracy score.
                </p>
              </div>
              <div className="rounded-lg border border-line bg-surface p-4 text-small text-ink-muted">
                <div className="flex items-center gap-2 mb-1">
                  <p className="font-medium text-ink">Label drift</p>
                  <HealthBadge status={q.data.drift.instrumented ? 'Healthy' : 'Planned'} />
                </div>
                {q.data.drift.instrumented ? (
                  <p>
                    Label churn for the live scoring version:{' '}
                    <span className="font-mono text-ink">{(q.data.drift.churn * 100).toFixed(1)}%</span>{' '}
                    of funds changed label ({displayLabel(q.data.drift.decision, 'decision')})
                    {q.data.drift.requires_human_review ? ' · review needed' : ''}. High churn ⇒ review the methodology.
                  </p>
                ) : (
                  <p>
                    Not enough labelled history yet to measure drift — a churn reading appears
                    once the live scoring version has labelled funds across more than one window.
                  </p>
                )}
              </div>
            </div>
          </section>
        )}
      </div>
    </>
  );
}
