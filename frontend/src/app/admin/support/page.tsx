'use client';

/**
 * Admin Support — /admin/support
 * Tier-A read-only page (Admin.md §14 Support).
 *
 * Sections:
 *   A — CAS parse-failure feed (job_id · user_id · status · error · created · completed)
 *   B — Support notes / tickets (not yet tracked — placeholder)
 *
 * Four-state contract: skeleton / empty / error+retry / data.
 * No advisory verbs. Triage only — no PII export.
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
import { useAdminCasFailures, type AdminCasFailure } from '@/features/admin/api';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------
function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2">
      {[...Array(rows)].map((_, i) => (
        <Skeleton key={i} className="h-11 rounded-md" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// CAS failures table
// ---------------------------------------------------------------------------
function CasFailuresTable({ failures }: { failures: AdminCasFailure[] }) {
  if (failures.length === 0) {
    return (
      <EmptyState
        title="No CAS parse failures"
        description="Failed CAS upload jobs will appear here once they are recorded."
        className="py-10"
      />
    );
  }

  const HEADERS = ['Job ID', 'User ID', 'Status', 'Error', 'Created', 'Completed'];

  // Derive badge status from job status string
  function jobBadgeStatus(status: string): 'Failed' | 'Running' | 'Success' | 'Warning' | 'Paused' {
    const s = status.toLowerCase();
    if (s === 'failed' || s === 'error') return 'Failed';
    if (s === 'running' || s === 'processing') return 'Running';
    if (s === 'done' || s === 'success' || s === 'complete' || s === 'completed') return 'Success';
    if (s === 'stuck' || s === 'timeout') return 'Warning';
    return 'Paused';
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <thead>
          <tr className="border-b border-line">
            {HEADERS.map((h) => (
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
          {failures.map((f) => (
            <tr
              key={f.job_id}
              className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors"
            >
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink">
                {f.job_id.length > 12 ? f.job_id.slice(0, 12) + '…' : f.job_id}
              </td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                {f.user_id.length > 8 ? f.user_id.slice(0, 8) + '…' : f.user_id}
              </td>
              <td className="py-2.5 pr-4">
                <HealthBadge status={jobBadgeStatus(f.status)} />
              </td>
              <td className="py-2.5 pr-4 text-small text-ink-secondary max-w-[260px] truncate">
                {f.error_message ?? '—'}
              </td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                {formatDateTime(f.created_at)}
              </td>
              <td className="py-2.5 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                {formatDateTime(f.completed_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Support page
// ---------------------------------------------------------------------------
export default function AdminSupportPage() {
  const casQ = useAdminCasFailures(50);

  return (
    <div className="flex flex-col gap-8">
      {/* Page header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-h2 font-medium text-ink">Support</h1>
          <p className="mt-1 text-small text-ink-muted">
            CAS parse-failure triage · support notes. Triage only — no PII export.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => casQ.refetch()}>
          <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
          Refresh
        </Button>
      </div>

      {/* Section A — CAS parse failures */}
      <section aria-labelledby="section-cas-failures">
        <Card>
          <CardHeader>
            <CardTitle id="section-cas-failures">CAS Parse Failures</CardTitle>
            <p className="mt-1 text-small text-ink-muted">
              Last 50 failed or stuck CAS upload jobs. Sourced from the stuck-CAS reaper signal.
            </p>
          </CardHeader>
          <CardBody>
            {casQ.isLoading && <TableSkeleton rows={6} />}
            {casQ.isError && (
              <ErrorCard
                title="Could not load CAS failures"
                onRetry={() => casQ.refetch()}
              />
            )}
            {casQ.data && <CasFailuresTable failures={casQ.data} />}
          </CardBody>
        </Card>
      </section>

      {/* Section B — Support notes placeholder */}
      <section aria-labelledby="section-support-notes">
        <Card>
          <CardHeader>
            <CardTitle id="section-support-notes">Support Notes / Tickets</CardTitle>
            <p className="mt-1 text-small text-ink-muted">
              Per-user support notes are surfaced in the User Detail drawer (Users & Audit page).
            </p>
          </CardHeader>
          <CardBody>
            <div className="rounded-lg border border-line bg-surface-2 px-5 py-4">
              <p className="text-small text-ink-muted">
                Support notes / tickets are not yet tracked on this page. Per-user notes are
                accessible via the User Detail drawer on the Users &amp; Audit page.
                A full support-ticket queue is planned for a future phase.
              </p>
            </div>
          </CardBody>
        </Card>
      </section>
    </div>
  );
}
