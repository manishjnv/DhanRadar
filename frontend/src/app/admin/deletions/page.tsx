'use client';

/**
 * Account deletions — /admin/deletions (DPDP B79 follow-up).
 *
 * Read-only console over the DPDP erasure lifecycle:
 *   - Summary chips: Waiting · Ready · Overdue
 *   - Pending table: erase/cancel actions (reuses the Phase-5 mutations from
 *     UserTable's Erase/Cancel flow — same hooks, same Idempotency-Key pattern)
 *   - Recently erased (90 days) — identity-free, nothing left to show once erased
 *   - Policy card — what we keep, in plain words, and the retention job's last run
 *
 * Four-state contract per section: Loading (skeleton) · Empty · Error+retry · Success.
 * No raw UUIDs on the surface; amber = waiting/needs-attention, red = overdue only.
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { formatDate, formatDateTime, formatRelative } from '@/components/admin/utils';
import {
  useAdminDeletions,
  useCancelDeletion,
  useEraseUser,
  type AdminPendingDeletion,
} from '@/features/admin/api';
import { ApiError } from '@/lib/apiClient';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// Section wrapper — mirrors the Users page pattern
// ---------------------------------------------------------------------------
function Section({
  id,
  title,
  subtitle,
  children,
  action,
}: {
  id: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section aria-labelledby={id}>
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle id={id}>{title}</CardTitle>
              {subtitle && <p className="mt-1 text-small text-ink-muted">{subtitle}</p>}
            </div>
            {action}
          </div>
        </CardHeader>
        <CardBody>{children}</CardBody>
      </Card>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Status badge — waiting (neutral) / ready (amber) / overdue (red)
// ---------------------------------------------------------------------------
function StatusBadge({ status }: { status: AdminPendingDeletion['status'] }) {
  const map: Record<AdminPendingDeletion['status'], { label: string; cls: string }> = {
    waiting: { label: 'Waiting', cls: 'bg-surface-2 text-ink-muted' },
    ready: { label: 'Ready to erase', cls: 'bg-amber/10 text-amber' },
    overdue: { label: 'Overdue', cls: 'bg-red/10 text-red' },
  };
  const { label, cls } = map[status];
  return (
    <span className={cn('rounded-full px-2 py-0.5 text-caption font-medium whitespace-nowrap', cls)}>
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Pending deletions table
// ---------------------------------------------------------------------------
type DialogKind = 'cancel' | 'erase' | null;

function PendingTable({ rows }: { rows: AdminPendingDeletion[] }) {
  const cancelMutation = useCancelDeletion();
  const eraseMutation = useEraseUser();
  const [dialog, setDialog] = React.useState<{ row: AdminPendingDeletion; kind: DialogKind }>({
    row: rows[0] ?? ({} as AdminPendingDeletion),
    kind: null,
  });

  function open(row: AdminPendingDeletion, kind: Exclude<DialogKind, null>) {
    setDialog({ row, kind });
  }
  function close() {
    setDialog((prev) => ({ ...prev, kind: null }));
  }

  if (rows.length === 0) {
    return <EmptyState title="No deletion requests." className="py-8" />;
  }

  const active = dialog.row;

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-small">
          <caption className="sr-only">Pending account deletions — oldest first</caption>
          <thead>
            <tr className="border-b border-line">
              {['Email', 'Requested', 'Can erase from', 'Erase by', 'Status', ''].map((h) => (
                <th
                  key={h || 'actions'}
                  scope="col"
                  className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const ready = row.status !== 'waiting';
              const eraseByDays = Math.max(
                0,
                Math.ceil((new Date(row.erase_by).getTime() - Date.now()) / (24 * 60 * 60 * 1000)),
              );
              return (
                <tr
                  key={row.user_id}
                  className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors"
                >
                  <td className="py-2.5 pr-4 text-ink-secondary text-[11px]">{row.email}</td>
                  <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                    {formatDate(row.requested_at)} · {formatRelative(row.requested_at)}
                  </td>
                  <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                    {formatDate(row.earliest_erase_at)}
                  </td>
                  <td
                    className={cn(
                      'py-2.5 pr-4 font-mono text-[11px] whitespace-nowrap',
                      row.status === 'overdue' ? 'text-red' : 'text-ink-muted',
                    )}
                  >
                    {formatDate(row.erase_by)}
                    {row.status !== 'overdue' && ` · ${eraseByDays}d left`}
                  </td>
                  <td className="py-2.5 pr-4">
                    <StatusBadge status={row.status} />
                  </td>
                  <td className="py-2.5">
                    <div className="flex items-center gap-1">
                      <Button size="sm" variant="ghost" onClick={() => open(row, 'cancel')}>
                        Cancel request
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-red hover:bg-red/10 disabled:hover:bg-transparent"
                        disabled={!ready}
                        title={ready ? undefined : `Can erase from ${formatDate(row.earliest_erase_at)}`}
                        onClick={() => open(row, 'erase')}
                      >
                        Erase permanently
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Cancel request dialog */}
      <ConfirmDialog
        open={dialog.kind === 'cancel'}
        onClose={close}
        title="Cancel deletion request"
        description={
          <>
            <strong>{active.email}</strong> will no longer be scheduled for deletion and can sign
            in again.
          </>
        }
        confirmLabel="Cancel request"
        confirmVariant="primary"
        onConfirm={async () => {
          await cancelMutation.mutateAsync(active.user_id);
        }}
      />

      {/* Erase permanently dialog */}
      <ConfirmDialog
        open={dialog.kind === 'erase'}
        onClose={close}
        title="Erase user permanently"
        description={
          <>
            This permanently deletes <strong>{active.email}</strong> and their portfolio data.
            This cannot be undone. Type the user&apos;s email to confirm.
          </>
        }
        confirmLabel="Erase permanently"
        confirmVariant="danger"
        confirmPhrase={active.email}
        onConfirm={async () => {
          try {
            const result = await eraseMutation.mutateAsync({
              id: active.user_id,
              idempotencyKey: crypto.randomUUID(),
            });
            const rows = Object.values(result.counts).reduce((sum, n) => sum + n, 0);
            toast.success(`Erased — ${rows} row${rows === 1 ? '' : 's'} removed.`);
          } catch (err) {
            if (err instanceof ApiError && err.problem.detail === 'erasure_wait_period') {
              const until = err.problem.earliest_erase_at;
              throw new Error(
                `Can erase from ${typeof until === 'string' ? formatDate(until) : 'later'}.`,
              );
            }
            throw err;
          }
        }}
      />
    </>
  );
}

// ---------------------------------------------------------------------------
// Recently erased table (90 days, identity-free)
// ---------------------------------------------------------------------------
function RecentErasuresTable({ rows }: { rows: { erased_at: string; rows_removed: number | null; erased_by: string }[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No erasures in the last 90 days"
        description="Completed erasures will appear here. Once erased, no user identity is kept."
        className="py-8"
      />
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <caption className="sr-only">Recently erased accounts — last 90 days</caption>
        <thead>
          <tr className="border-b border-line">
            {['Date', 'Records removed', 'By'].map((h) => (
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
          {rows.map((row, i) => (
            <tr key={`${row.erased_at}-${i}`} className="border-b border-line last:border-0">
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                {formatDateTime(row.erased_at)}
              </td>
              <td className="py-2.5 pr-4 text-ink">{row.rows_removed ?? '—'}</td>
              <td className="py-2.5 text-ink-secondary">{row.erased_by}</td>
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
export default function AdminDeletionsPage() {
  const deletionsQ = useAdminDeletions();

  const waiting = deletionsQ.data?.pending.filter((r) => r.status === 'waiting').length ?? 0;
  const ready = deletionsQ.data?.pending.filter((r) => r.status === 'ready').length ?? 0;
  const overdue = deletionsQ.data?.pending.filter((r) => r.status === 'overdue').length ?? 0;

  return (
    <div className="flex flex-col gap-8">
      {/* Page header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-h2 font-medium text-ink">Account deletions</h1>
          <p className="mt-1 text-small text-ink-muted">
            DPDP right-to-erasure requests — waiting period, erase window, and what we keep.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => deletionsQ.refetch()}>
          <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
          Refresh
        </Button>
      </div>

      {deletionsQ.isError && (
        <ErrorCard
          title="Could not load account deletions"
          onRetry={() => deletionsQ.refetch()}
          className="max-w-md"
        />
      )}

      {deletionsQ.isLoading && (
        <div className="grid grid-cols-3 gap-3 max-w-lg">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
      )}

      {deletionsQ.data && (
        <>
          {/* Summary chips */}
          <div className="grid grid-cols-3 gap-3 max-w-lg">
            <Card className="p-4">
              <p className="text-caption text-ink-muted">Waiting</p>
              <p className="mt-1 text-h2 font-medium text-ink">{waiting}</p>
            </Card>
            <Card className="p-4">
              <p className="text-caption text-ink-muted">Ready</p>
              <p className={cn('mt-1 text-h2 font-medium', ready > 0 ? 'text-amber' : 'text-ink')}>
                {ready}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-caption text-ink-muted">Overdue</p>
              <p className={cn('mt-1 text-h2 font-medium', overdue > 0 ? 'text-red' : 'text-ink')}>
                {overdue}
              </p>
            </Card>
          </div>

          {/* Pending table */}
          <Section
            id="section-pending-deletions"
            title="Pending requests"
            subtitle="Oldest first. Erase permanently unlocks once the 7-day wait period has passed."
          >
            <PendingTable rows={deletionsQ.data.pending} />
          </Section>

          {/* Recently erased */}
          <Section id="section-recent-erasures" title="Recently erased" subtitle="Last 90 days.">
            <RecentErasuresTable rows={deletionsQ.data.recent_erasures} />
          </Section>

          {/* Policy */}
          <Section
            id="section-retention-policy"
            title="What we keep after deletion"
            subtitle="A small set of legally-required records survive erasure, tied to a random ID only — no name or email."
          >
            <div className="flex flex-col gap-4">
              <ul className="flex flex-col gap-0">
                {deletionsQ.data.policy.retention.map((row) => (
                  <li
                    key={row.label}
                    className="flex items-center justify-between gap-4 border-b border-line py-2 last:border-0 text-small"
                  >
                    <span className="text-ink">{row.label}</span>
                    <span className="text-ink-muted">
                      kept {Math.round(row.keep_days / 365)} year{Math.round(row.keep_days / 365) === 1 ? '' : 's'}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="text-caption text-ink-faint">
                Retention clean-up:{' '}
                {deletionsQ.data.retention_job?.last_run_at
                  ? `last run ${formatDateTime(deletionsQ.data.retention_job.last_run_at)} (${deletionsQ.data.retention_job.result ?? 'unknown'})`
                  : 'not run yet'}
              </p>
            </div>
          </Section>
        </>
      )}
    </div>
  );
}
