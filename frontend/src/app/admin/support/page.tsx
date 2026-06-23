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
import { formatDateTime, formatRelative } from '@/components/admin/utils';
import { Input } from '@/components/ui/Input';
import { useAdminCasFailures, useSetCasNotes, type AdminCasFailure } from '@/features/admin/api';
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
// CAS failure row — with inline support-note editor
// ---------------------------------------------------------------------------
type BadgeStatus = 'Failed' | 'Running' | 'Success' | 'Warning' | 'Paused';

function CasFailureRow({ f, badgeStatus }: { f: AdminCasFailure; badgeStatus: BadgeStatus }) {
  const setNotes = useSetCasNotes();
  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState(f.support_notes ?? '');
  const [justSaved, setJustSaved] = React.useState(false);

  // Re-sync the draft if the underlying note changes (e.g. after a refetch)
  // and we are not actively editing.
  React.useEffect(() => {
    if (!editing) setDraft(f.support_notes ?? '');
  }, [f.support_notes, editing]);

  function handleSave() {
    setNotes.mutate(
      { jobId: f.job_id, notes: draft.trim() },
      {
        onSuccess: () => {
          setEditing(false);
          setJustSaved(true);
          window.setTimeout(() => setJustSaved(false), 2000);
        },
      },
    );
  }

  return (
    <tr className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors">
      <td className="py-2.5 pr-4 font-mono text-[11px] text-ink">
        {f.job_id.length > 12 ? f.job_id.slice(0, 12) + '…' : f.job_id}
      </td>
      <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
        {f.user_id.length > 8 ? f.user_id.slice(0, 8) + '…' : f.user_id}
      </td>
      <td className="py-2.5 pr-4">
        <HealthBadge status={badgeStatus} />
      </td>
      <td
        className="py-2.5 pr-4 text-small text-ink-secondary max-w-[260px] truncate"
        title={f.error_message ?? undefined}
      >
        {f.error_message ?? '—'}
      </td>
      <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap">
        {formatDateTime(f.created_at)}
      </td>
      <td
        className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap"
        title={f.completed_at ? undefined : 'Stuck jobs have no completion time — this is expected.'}
      >
        {f.completed_at ? formatDateTime(f.completed_at) : '—'}
      </td>
      <td className="py-2.5 align-top min-w-[220px]">
        {editing ? (
          <div className="flex flex-col gap-1.5">
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Add a support note…"
              aria-label={`Support note for job ${f.job_id}`}
              maxLength={2000}
              disabled={setNotes.isPending}
              className="h-8 text-small"
            />
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={handleSave}
                disabled={setNotes.isPending}
              >
                {setNotes.isPending ? 'Saving…' : 'Save'}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setEditing(false);
                  setDraft(f.support_notes ?? '');
                }}
                disabled={setNotes.isPending}
              >
                Cancel
              </Button>
              {setNotes.isError && (
                <span className="text-caption text-danger">Could not save</span>
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-2">
            <span
              className={cn(
                'text-small max-w-[200px] break-words',
                f.support_notes ? 'text-ink-secondary' : 'text-ink-faint',
              )}
            >
              {f.support_notes || '—'}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setEditing(true)}
              aria-label={`Edit support note for job ${f.job_id}`}
            >
              {f.support_notes ? 'Edit' : 'Add'}
            </Button>
            {justSaved && <span className="text-caption text-success">Saved</span>}
          </div>
        )}
      </td>
    </tr>
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

  const HEADERS = ['Upload Job', 'User ID', 'Status', 'Error', 'Created', 'Completed', 'Support Note'];

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
        <caption className="sr-only">Failed CAS upload jobs — job ID, status, error, and timestamps</caption>
        <thead>
          <tr className="border-b border-line">
            {HEADERS.map((h) => (
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
          {failures.map((f) => (
            <CasFailureRow key={f.job_id} f={f} badgeStatus={jobBadgeStatus(f.status)} />
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
  const [lastRefreshed, setLastRefreshed] = React.useState<Date | null>(null);
  function handleRefresh() {
    casQ.refetch();
    setLastRefreshed(new Date());
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Page header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-h2 font-medium text-ink">Support</h1>
          <p className="mt-1 text-small text-ink-muted">
            CAS upload failure triage · support notes. Triage only — no PII export.
          </p>
        </div>
        <div className="flex flex-col items-end gap-0.5">
          <Button variant="ghost" size="sm" onClick={handleRefresh}>
            <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
            Refresh
          </Button>
          {lastRefreshed && (
            <span className="text-caption text-ink-faint">
              Last updated {formatRelative(lastRefreshed.toISOString())}
            </span>
          )}
        </div>
      </div>

      {/* Section A — Failed CAS uploads */}
      <section aria-labelledby="section-cas-failures">
        <Card>
          <CardHeader>
            <CardTitle id="section-cas-failures">Failed CAS Uploads</CardTitle>
            <p className="mt-1 text-small text-ink-muted">
              Mutual-fund statement uploads that failed or got stuck.
            </p>
          </CardHeader>
          <CardBody>
            <p className="mb-4 text-small text-ink-muted">
              A CAS upload failure means the system could not parse or process a user&apos;s
              mutual-fund statement (CAS). To triage: find the matching user via the
              Users &amp; Audit page using the User ID below.
              Stuck jobs (no completion time) are held by the reaper until manually cleared.
            </p>
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
