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
import { formatDateTime } from '@/components/admin/utils';
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
  'Version', 'Created by', 'Approved by', '2-person OK', 'Active', 'Activated at', 'Created at',
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
        <thead>
          <tr className="border-b border-line">
            {VERSION_HEADERS.map((h) => (
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
          {versions.map((v) => (
            <tr
              key={v.model_version}
              className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors"
            >
              <td className="py-2.5 pr-4 font-mono text-[11px] font-medium text-ink whitespace-nowrap">
                {v.model_version}
              </td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                {v.created_by
                  ? (v.created_by.length > 8 ? v.created_by.slice(0, 8) + '…' : v.created_by)
                  : '—'}
              </td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                {v.approved_by
                  ? (v.approved_by.length > 8 ? v.approved_by.slice(0, 8) + '…' : v.approved_by)
                  : '—'}
              </td>
              <td className="py-2.5 pr-4">
                <HealthBadge status={v.two_person_ok ? 'Success' : 'Warning'} />
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
              Read-only view of <code className="font-mono text-caption">ranking_configs</code> registry versions.
              Promotion requires two-person gate (B6) + separate human approval — Phase 5.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="ghost"
              disabled
              title="Promote version — Phase 5 (two-person gate B6 + human approval required)"
              className="opacity-40 cursor-not-allowed"
            >
              Promote version — Phase 5 (two-person gate)
            </Button>
            <Button variant="ghost" size="sm" onClick={() => q.refetch()}>
              <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Section A — Registry versions */}
        <section aria-labelledby="section-ai-versions">
          <Card>
            <CardHeader>
              <CardTitle id="section-ai-versions">Registry Versions</CardTitle>
              <p className="mt-1 text-small text-ink-muted">
                All model versions in the scoring registry.
                Activation requires the two-person methodology gate.
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

        {/* Section B — Not-yet-instrumented notes */}
        {q.data && (
          <section aria-labelledby="section-ai-gaps" className="flex flex-col gap-3">
            <h2 id="section-ai-gaps" className="text-h3 font-medium text-ink">
              Planned Instrumentation
            </h2>
            <div className="flex flex-col gap-2">
              <div className="rounded-lg border border-line bg-surface p-4 text-small text-ink-muted">
                <p className="font-medium text-ink mb-1">Backtest vs benchmark</p>
                <p>
                  Not yet instrumented —{' '}
                  <HealthBadge status={q.data.backtest.instrumented ? 'Healthy' : 'Planned'} />{' '}
                  Offline backtest tooling is tracked in the Phase 5 build plan.
                </p>
              </div>
              <div className="rounded-lg border border-line bg-surface p-4 text-small text-ink-muted">
                <p className="font-medium text-ink mb-1">Model drift detection</p>
                <p>
                  Not yet instrumented —{' '}
                  <HealthBadge status={q.data.drift.instrumented ? 'Healthy' : 'Planned'} />{' '}
                  Drift alerts will be added alongside the backtest harness.
                </p>
              </div>
            </div>
          </section>
        )}
      </div>
    </>
  );
}
