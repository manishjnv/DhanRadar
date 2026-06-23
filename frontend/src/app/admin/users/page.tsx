'use client';

/**
 * Admin Users & Audit — /admin/users
 *
 * Section A: User Summary StatCard row (Total · Active · Premium · Trials · Blocked)
 * Section B: UserTable with search + filter chips; [View] opens SideDrawer with user detail.
 *            [Suspend] [Unsuspend] [Reset Access] now live via ConfirmDialog (Phase 5).
 * Section C: Subscription Metrics StatCard row (premium_count · trials · renewals_30d · churn_30d)
 * Section D: Audit table (Timestamp · Actor · Action · Entity · Result) with date/action filters.
 *
 * Four-state contract per section: Default · Loading (skeleton) · Empty · Error+Retry
 * Numeric values ARE allowed (admin-only, Admin.md §16).
 * No advisory verbs.
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { StatCard } from '@/components/admin/StatCard';
import { HealthBadge } from '@/components/admin/HealthBadge';
import { SideDrawer } from '@/components/admin/SideDrawer';
import { UserTable } from '@/components/admin/UserTable';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { formatRelative, formatDateTime } from '@/components/admin/utils';
import {
  useAdminUserSummary,
  useAdminUsers,
  useAdminUserDetail,
  useAdminBillingSubMetrics,
  useAdminAudit,
  useSuspendUser,
  useUnsuspendUser,
  useResetUserAccess,
  type AdminAuditRow,
  type AdminUserDetail,
} from '@/features/admin/api';
import { displayLabel } from '@/lib/displayLabel';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// Skeletons
// ---------------------------------------------------------------------------
function StatRowSkeleton({ cols = 5 }: { cols?: number }) {
  // Static class map — Tailwind JIT cannot see interpolated class names.
  const lg = cols === 4 ? 'lg:grid-cols-4' : 'lg:grid-cols-5';
  return (
    <div className={`grid grid-cols-2 gap-3 sm:grid-cols-3 ${lg}`}>
      {[...Array(cols)].map((_, i) => (
        <Skeleton key={i} className="h-24 rounded-xl" />
      ))}
    </div>
  );
}

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
// Section wrapper — mirrors operations page pattern
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
// User Detail Drawer content
// ---------------------------------------------------------------------------
function UserDetailContent({ userId }: { userId: string }) {
  const { data, isLoading, isError } = useAdminUserDetail(userId);
  const suspendMutation      = useSuspendUser();
  const unsuspendMutation    = useUnsuspendUser();
  const resetAccessMutation  = useResetUserAccess();

  const [dialog, setDialog] = React.useState<'suspend' | 'unsuspend' | 'reset-access' | null>(null);
  const [suspendReason, setSuspendReason] = React.useState('');

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-8 rounded" />)}
      </div>
    );
  }

  if (isError || !data) {
    return <ErrorCard title="Could not load user detail" />;
  }

  const statusBadge = (
    data.status === 'active'    ? 'Healthy'  :
    data.status === 'suspended' ? 'Failed'   :
    data.status === 'blocked'   ? 'Critical' :
    'Paused'
  );

  const profileRows: Array<{ label: string; value: React.ReactNode }> = [
    { label: 'ID',                   value: <span className="font-mono text-[11px]">{data.id}</span> },
    { label: 'Display Name',         value: data.display_name || '—' },
    { label: 'Email',                value: data.email },
    { label: 'Plan',                 value: displayLabel(data.tier, 'tier') },
    { label: 'Status',               value: <HealthBadge status={statusBadge} /> },
    ...(data.status === 'suspended' && data.pro_access_reason
      ? [{ label: 'Suspend Reason',  value: <span className="text-red">{data.pro_access_reason}</span> }]
      : []),
    { label: 'Joined',               value: formatDateTime(data.created_at) },
    { label: 'Paid Access Until',    value: data.pro_access_until ? formatDateTime(data.pro_access_until) : '—' },
    { label: 'Access Grant Reason',  value: data.pro_access_reason || '—' },
    { label: 'Consent Version',      value: data.dpdp_consent_version || '—' },
    {
      label: 'Last Login',
      value: data.last_login_at ? (
        formatDateTime(data.last_login_at)
      ) : (
        <span className="text-ink-muted" title="No login recorded since login tracking went live.">
          Never
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* Profile */}
      <div>
        <h3 className="mb-3 text-h3 font-medium text-ink">Profile</h3>
        <dl className="flex flex-col gap-0">
          {profileRows.map(({ label, value }) => (
            <div
              key={label}
              className="flex items-start justify-between gap-4 border-b border-line py-2 last:border-0"
            >
              <dt className="text-small text-ink-muted shrink-0 w-36">{label}</dt>
              <dd className="text-small text-ink text-right">{value}</dd>
            </div>
          ))}
        </dl>
      </div>

      {/* Subscription */}
      <div>
        <h3 className="mb-3 text-h3 font-medium text-ink">Subscription</h3>
        {data.subscription ? (
          <dl className="flex flex-col gap-0">
            {([
              ['Plan',        data.subscription.plan],
              ['Status',      data.subscription.status],
              ['Period End',  data.subscription.current_period_end
                                ? formatDateTime(data.subscription.current_period_end)
                                : '—'],
            ] as [string, string][]).map(([label, value]) => (
              <div
                key={label}
                className="flex items-start justify-between gap-4 border-b border-line py-2 last:border-0"
              >
                <dt className="text-small text-ink-muted w-36">{label}</dt>
                <dd className="text-small text-ink text-right">{value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-small text-ink-muted">No active subscription.</p>
        )}
      </div>

      {/* Payments */}
      <div>
        <h3 className="mb-3 text-h3 font-medium text-ink">Payments</h3>
        {data.payments.length === 0 ? (
          <p className="text-small text-ink-muted">No payments recorded.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {data.payments.map((p, i) => (
              <div key={i} className="rounded-lg border border-line bg-surface-2 p-3 text-small">
                <div className="flex items-center justify-between gap-2">
                  <span className={cn(
                    'font-medium',
                    p.status === 'captured' ? 'text-emerald' :
                    p.status === 'failed'   ? 'text-red' : 'text-ink',
                  )}>
                    {p.status}
                  </span>
                  <span className="font-mono text-[11px] text-ink-muted">{formatDateTime(p.ts)}</span>
                </div>
                {p.razorpay_payment_id && (
                  <p className="mt-1 font-mono text-[11px] text-ink-muted">{p.razorpay_payment_id}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Login history & CAS uploads — not yet unified */}
      <div>
        <h3 className="mb-3 text-h3 font-medium text-ink">Login History</h3>
        <p className="text-small text-ink-muted">Not yet tracked.</p>
      </div>
      <div>
        <h3 className="mb-3 text-h3 font-medium text-ink">CAS Upload History</h3>
        <p className="text-small text-ink-muted">Not yet tracked.</p>
      </div>

      {/* Admin actions */}
      <div className="flex flex-col gap-2 pt-2">
        <p className="text-caption text-ink-faint uppercase tracking-wide font-medium">Admin Actions</p>
        <div className="flex flex-wrap gap-2">
          {data.status === 'suspended' ? (
            <Button size="sm" variant="ghost" onClick={() => setDialog('unsuspend')}>
              Unsuspend
            </Button>
          ) : data.status === 'active' ? (
            <Button size="sm" variant="ghost" onClick={() => { setSuspendReason(''); setDialog('suspend'); }}>
              Suspend
            </Button>
          ) : null}
          <Button size="sm" variant="ghost" onClick={() => setDialog('reset-access')}>
            Reset Access
          </Button>
        </div>
      </div>

      {/* Suspend dialog */}
      <ConfirmDialog
        open={dialog === 'suspend'}
        onClose={() => setDialog(null)}
        title="Suspend user"
        description={
          <>
            <strong>{data.email}</strong> will lose all access until manually unsuspended.
            Active sessions remain valid until they expire. Enter a reason then type the email to confirm.
          </>
        }
        confirmLabel="Suspend"
        confirmVariant="danger"
        confirmPhrase={data.email}
        onConfirm={async () => {
          await suspendMutation.mutateAsync({ id: userId, reason: suspendReason || undefined });
        }}
      >
        <div className="flex flex-col gap-1.5">
          <label htmlFor="drawer-suspend-reason" className="text-small font-medium text-ink">
            Reason <span className="text-ink-muted font-normal">(optional)</span>
          </label>
          <input
            id="drawer-suspend-reason"
            type="text"
            value={suspendReason}
            onChange={(e) => setSuspendReason(e.target.value)}
            placeholder="e.g. Terms of service violation"
            className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-royal/40"
          />
        </div>
      </ConfirmDialog>

      {/* Unsuspend dialog */}
      <ConfirmDialog
        open={dialog === 'unsuspend'}
        onClose={() => setDialog(null)}
        title="Unsuspend user"
        description={<><strong>{data.email}</strong> will regain normal access.</>}
        confirmLabel="Unsuspend"
        onConfirm={async () => {
          await unsuspendMutation.mutateAsync(userId);
        }}
      />

      {/* Reset Access dialog */}
      <ConfirmDialog
        open={dialog === 'reset-access'}
        onClose={() => setDialog(null)}
        title="Reset user access"
        description="Clears the login lockout counters for this user (the brute-force limits for TOTP and email OTP). It does not change the user's plan, access grants, or account status."
        confirmLabel="Reset Access"
        confirmVariant="danger"
        confirmPhrase={data.email}
        onConfirm={async () => {
          await resetAccessMutation.mutateAsync(userId);
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Audit table (Section D)
// ---------------------------------------------------------------------------
function AuditTable({ rows }: { rows: AdminAuditRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No audit entries"
        description="Admin actions will appear here once recorded."
        className="py-8"
      />
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <caption className="sr-only">Admin audit log — recent admin actions and their outcomes</caption>
        <thead>
          <tr className="border-b border-line">
            {['Timestamp', 'Actor', 'Action', 'Entity', 'Result'].map((h) => (
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
          {rows.map((row) => {
            // Normalize ok/success both to "Success"
            const resultLabel = (row.result === 'ok' || row.result === 'success') ? 'Success' : row.result;
            const resultOk    = row.result === 'ok' || row.result === 'success';

            // Entity: "user:uuid" → "User {uuid8}…" with full-id tooltip
            let entityDisplay: React.ReactNode = '—';
            if (row.target_type && row.target_id) {
              const short = row.target_id.length > 8 ? row.target_id.slice(0, 8) + '…' : row.target_id;
              const fullId = `${row.target_type}:${row.target_id}`;
              const typeLabel = row.target_type.charAt(0).toUpperCase() + row.target_type.slice(1);
              entityDisplay = (
                <span title={fullId} className="cursor-default">
                  {typeLabel} {short}
                </span>
              );
            } else if (row.target_type) {
              entityDisplay = row.target_type;
            }

            return (
              <tr key={row.id} className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors">
                <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                  {formatDateTime(row.ts)}
                </td>
                <td className="py-2.5 pr-4 font-mono text-[11px] text-ink">
                  {row.admin_id.slice(0, 8)}…
                </td>
                <td className="py-2.5 pr-4 font-medium text-ink">
                  {displayLabel(row.action, 'audit')}
                </td>
                <td className="py-2.5 pr-4 text-ink-secondary text-[11px]">
                  {entityDisplay}
                </td>
                <td className="py-2.5">
                  <span
                    className={cn(
                      'rounded-full px-2 py-0.5 text-caption font-medium',
                      resultOk ? 'bg-emerald/10 text-emerald' : 'bg-red/10 text-red',
                    )}
                  >
                    {resultLabel}
                  </span>
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
// Audit filter controls
// ---------------------------------------------------------------------------
function AuditFilters({
  actionFilter,
  setActionFilter,
  onRefetch,
}: {
  actionFilter: string;
  setActionFilter: (v: string) => void;
  onRefetch: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="text"
        placeholder="Filter by action…"
        value={actionFilter}
        onChange={(e) => setActionFilter(e.target.value)}
        className="h-8 rounded-md border border-line bg-surface px-3 text-small text-ink placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-royal/40"
      />
      <Button size="sm" variant="ghost" onClick={onRefetch}>
        <RefreshCw size={12} strokeWidth={2} aria-hidden="true" />
        Refresh
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Users page
// ---------------------------------------------------------------------------
export default function AdminUsersPage() {
  // Section B — user list filters
  const [search, setSearch] = React.useState('');
  const [debouncedSearch, setDebouncedSearch] = React.useState('');
  const [planFilter, setPlanFilter] = React.useState('');
  const [statusFilter, setStatusFilter] = React.useState('');

  // Debounce search 300 ms
  React.useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Section D — audit filters
  const [auditAction, setAuditAction] = React.useState('');

  // Drawer state
  const [viewUserId, setViewUserId] = React.useState<string | null>(null);

  // Data hooks
  const summaryQ       = useAdminUserSummary();
  const usersQ         = useAdminUsers({
    search: debouncedSearch || undefined,
    plan:   planFilter || undefined,
    status: statusFilter || undefined,
    limit: 50,
  });
  const subMetricsQ    = useAdminBillingSubMetrics();
  const auditQ         = useAdminAudit({
    action: auditAction || undefined,
    limit: 100,
  });

  const PLAN_OPTIONS   = ['', 'free', 'trial', 'plus', 'founder_lifetime'];
  // 'blocked' is not a valid backend status; map to 'deletion_requested' with label "Deletion Requested"
  const STATUS_OPTIONS: Array<{ value: string; label: string }> = [
    { value: '',                   label: 'All status' },
    { value: 'active',             label: 'Active' },
    { value: 'suspended',          label: 'Suspended' },
    { value: 'deletion_requested', label: 'Deletion Requested' },
  ];

  const [lastRefreshed, setLastRefreshed] = React.useState<Date | null>(null);
  function handleRefreshAll() {
    summaryQ.refetch();
    usersQ.refetch();
    subMetricsQ.refetch();
    auditQ.refetch();
    setLastRefreshed(new Date());
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Page header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-h2 font-medium text-ink">Users & Audit</h1>
          <p className="mt-1 text-small text-ink-muted">
            User management · subscriptions · audit log
          </p>
        </div>
        <div className="flex flex-col items-end gap-0.5">
          <Button variant="ghost" size="sm" onClick={handleRefreshAll}>
            <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
            Refresh all
          </Button>
          {lastRefreshed && (
            <span className="text-caption text-ink-faint">
              Last updated {formatRelative(lastRefreshed.toISOString())}
            </span>
          )}
        </div>
      </div>

      {/* Section A — User Summary */}
      <section aria-labelledby="section-user-summary">
        <h2 id="section-user-summary" className="mb-3 text-h3 font-medium text-ink">
          User Summary
        </h2>
        {summaryQ.isLoading && <StatRowSkeleton cols={5} />}
        {summaryQ.isError && (
          <ErrorCard
            title="Could not load user summary"
            onRetry={() => summaryQ.refetch()}
            className="max-w-md"
          />
        )}
        {summaryQ.data && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard title="Total Users" value={summaryQ.data.total.toLocaleString('en-IN')} status="neutral" />
            <StatCard title="Active"      value={summaryQ.data.active.toLocaleString('en-IN')} status="healthy" />
            <StatCard
              title="Premium"
              value={summaryQ.data.premium.toLocaleString('en-IN')}
              status="neutral"
              sub="Users on paid plans"
            />
            <StatCard
              title="Trials"
              value={summaryQ.data.trials.toLocaleString('en-IN')}
              status="neutral"
              sub="Users with a paid-access trial"
            />
            <StatCard
              title="Blocked"
              value={summaryQ.data.blocked.toLocaleString('en-IN')}
              status={summaryQ.data.blocked > 0 ? 'warning' : 'neutral'}
              sub="Users who requested deletion"
            />
          </div>
        )}
      </section>

      {/* Section B — User List */}
      <Section
        id="section-user-list"
        title="User List"
        subtitle="Search and filter users. Suspend, Unsuspend, and Reset Access are now live (Phase 5)."
        action={
          <div className="flex flex-wrap items-center gap-2">
            {/* Search */}
            <input
              type="text"
              placeholder="Search name or email…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 rounded-md border border-line bg-surface px-3 text-small text-ink placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-royal/40"
            />
            {/* Plan filter chips */}
            <div className="flex items-center gap-1">
              {PLAN_OPTIONS.map((opt) => (
                <button
                  key={opt || 'all-plans'}
                  onClick={() => setPlanFilter(opt)}
                  className={cn(
                    'rounded-full px-2.5 py-0.5 text-caption font-medium transition-colors',
                    planFilter === opt
                      ? 'bg-royal/10 text-royal'
                      : 'bg-surface-2 text-ink-muted hover:bg-surface-3',
                  )}
                >
                  {opt ? displayLabel(opt, 'tier') : 'All plans'}
                </button>
              ))}
            </div>
            {/* Status filter chips */}
            <div className="flex items-center gap-1">
              {STATUS_OPTIONS.map(({ value, label }) => (
                <button
                  key={value || 'all-status'}
                  onClick={() => setStatusFilter(value)}
                  className={cn(
                    'rounded-full px-2.5 py-0.5 text-caption font-medium transition-colors',
                    statusFilter === value
                      ? 'bg-royal/10 text-royal'
                      : 'bg-surface-2 text-ink-muted hover:bg-surface-3',
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        }
      >
        {usersQ.isLoading && <TableSkeleton rows={8} />}
        {usersQ.isError && (
          <ErrorCard
            title="Could not load users"
            onRetry={() => usersQ.refetch()}
          />
        )}
        {usersQ.data && usersQ.data.users.length === 0 && (
          <EmptyState
            title="No users found"
            description="Try adjusting your search or filters."
            className="py-8"
          />
        )}
        {usersQ.data && usersQ.data.users.length > 0 && (
          <>
            <p className="mb-3 text-caption text-ink-muted">
              Showing {usersQ.data.users.length} of {usersQ.data.total.toLocaleString('en-IN')} users
            </p>
            <UserTable
              users={usersQ.data.users}
              onView={(id) => setViewUserId(id)}
            />
          </>
        )}
      </Section>

      {/* Section C — Subscription Metrics */}
      <section aria-labelledby="section-sub-metrics">
        <h2 id="section-sub-metrics" className="mb-3 text-h3 font-medium text-ink">
          Subscription Metrics
        </h2>
        {subMetricsQ.isLoading && <StatRowSkeleton cols={4} />}
        {subMetricsQ.isError && (
          <ErrorCard
            title="Could not load subscription metrics"
            onRetry={() => subMetricsQ.refetch()}
            className="max-w-md"
          />
        )}
        {subMetricsQ.data && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard title="Premium"      value={subMetricsQ.data.premium_count.toLocaleString('en-IN')} status="neutral" />
            <StatCard title="Trials"       value={subMetricsQ.data.trials.toLocaleString('en-IN')}        status="neutral" />
            <StatCard title="Renewals 30d" value={subMetricsQ.data.renewals_30d.toLocaleString('en-IN')}  status="healthy" />
            <StatCard
              title="Churn 30d"
              value={subMetricsQ.data.churn_30d.toLocaleString('en-IN')}
              status={subMetricsQ.data.churn_30d > 0 ? 'warning' : 'neutral'}
            />
          </div>
        )}
      </section>

      {/* Section D — Activity & Audit Log */}
      <Section
        id="section-audit"
        title="Activity & Audit Log"
        subtitle="Showing admin actions only — user-activity events (logins, uploads) are not yet unified."
        action={
          <AuditFilters
            actionFilter={auditAction}
            setActionFilter={setAuditAction}
            onRefetch={() => auditQ.refetch()}
          />
        }
      >
        {auditQ.isLoading && <TableSkeleton rows={6} />}
        {auditQ.isError && (
          <ErrorCard
            title="Could not load audit log"
            onRetry={() => auditQ.refetch()}
          />
        )}
        {auditQ.data && <AuditTable rows={auditQ.data} />}
      </Section>

      {/* User detail drawer */}
      <SideDrawer
        title={`User Detail${viewUserId ? ` — ${viewUserId.slice(0, 8)}` : ''}`}
        open={!!viewUserId}
        onClose={() => setViewUserId(null)}
        width="w-[540px]"
      >
        {viewUserId && <UserDetailContent userId={viewUserId} />}
      </SideDrawer>
    </div>
  );
}
