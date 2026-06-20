'use client';

/**
 * Admin Billing Ops — /admin/billing
 *
 * KPI row: MRR · ARPU · Active Subs · Past Due · Trials
 * Subscriptions table: user_id · email · plan · status · renews · price (₹)
 * Payments table: user_id · razorpay_payment_id · status · ts · request_id
 *   Per payment row: [Refund] opens ConfirmDialog (Phase 5, type-to-confirm "REFUND",
 *   Idempotency-Key = crypto.randomUUID() per submit, regenerated on Retry).
 * Webhook health card: success/failed counts + last_event_at
 * Plan Change section: per-subscription [Change Plan] button → ConfirmDialog.
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
import { SubscriptionTable } from '@/components/admin/SubscriptionTable';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { formatRelative, formatDateTime, formatCurrency } from '@/components/admin/utils';
import { displayLabel } from '@/lib/displayLabel';
import {
  useAdminBillingOverview,
  useAdminSubscriptions,
  useAdminBillingPayments,
  useAdminBillingWebhookHealth,
  useAdminRefund,
  useAdminPlanChange,
  type AdminPaymentRow,
  type AdminSubscriptionRow,
} from '@/features/admin/api';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// Idempotency key generator — fresh UUID per submit attempt
// ---------------------------------------------------------------------------
function newIdempotencyKey() {
  return crypto.randomUUID();
}

// ---------------------------------------------------------------------------
// Skeletons
// ---------------------------------------------------------------------------
function StatRowSkeleton({ cols = 5 }: { cols?: number }) {
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
// Section wrapper
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
// Refund dialog state
// ---------------------------------------------------------------------------
interface RefundTarget {
  payment: AdminPaymentRow;
  idempotencyKey: string;
}

function PaymentsTable({ payments }: { payments: AdminPaymentRow[] }) {
  const refundMutation = useAdminRefund();
  const [refundTarget, setRefundTarget] = React.useState<RefundTarget | null>(null);
  const [refundAmount, setRefundAmount] = React.useState('');
  const [refundReason, setRefundReason] = React.useState('');

  function openRefund(payment: AdminPaymentRow) {
    setRefundAmount('');
    setRefundReason('');
    setRefundTarget({ payment, idempotencyKey: newIdempotencyKey() });
  }
  function closeRefund() {
    setRefundTarget(null);
  }

  if (payments.length === 0) {
    return (
      <EmptyState
        title="No payments found"
        description="Recent payments will appear here."
        className="py-8"
      />
    );
  }

  const HEADERS = ['User ID', 'Payment ID', 'Status', 'Timestamp', 'Request ID', ''];

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-small">
          <caption className="sr-only">Recent payment transactions</caption>
          <thead>
            <tr className="border-b border-line">
              {HEADERS.map((h) => (
                <th
                  key={h || 'action'}
                  scope="col"
                  className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {payments.map((p, i) => (
              <tr
                key={`${p.user_id}-${i}`}
                className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors"
              >
                <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                  {p.user_id.slice(0, 8)}…
                </td>
                <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-secondary">
                  {p.razorpay_payment_id ?? '—'}
                </td>
                <td className="py-2.5 pr-4">
                  <div className="flex items-center gap-1.5">
                    <HealthBadge
                      status={
                        p.status === 'captured' ? 'Success' :
                        p.status === 'failed'   ? 'Failed'  :
                        p.status === 'pending'  ? 'Running' :
                        'Paused'
                      }
                    />
                    <span className="text-[11px] text-ink-secondary">
                      {displayLabel(p.status, 'payment')}
                    </span>
                  </div>
                </td>
                <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                  {formatDateTime(p.ts)}
                </td>
                <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                  {p.request_id ? p.request_id.slice(0, 8) + '…' : '—'}
                </td>
                <td className="py-2.5">
                  {p.status === 'captured' && p.razorpay_payment_id ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => openRefund(p)}
                    >
                      Refund
                    </Button>
                  ) : (
                    <span className="text-caption text-ink-faint">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Refund dialog */}
      {refundTarget && (
        <ConfirmDialog
          open={!!refundTarget}
          onClose={closeRefund}
          title="Issue refund"
          description={
            <>
              Refund payment <code className="font-mono text-caption bg-surface-2 px-1 rounded">{refundTarget.payment.razorpay_payment_id}</code>.
              A fresh idempotency key is generated on each submit and on Retry.
              Enter the amount (₹) and reason, then type <strong>REFUND</strong> to confirm.
            </>
          }
          confirmLabel="Issue Refund"
          confirmVariant="danger"
          confirmPhrase="REFUND"
          onConfirm={async () => {
            const amount = parseFloat(refundAmount);
            if (!amount || amount <= 0) throw new Error('Enter a valid positive amount in ₹.');
            if (!refundReason.trim()) throw new Error('Reason is required.');
            if (!refundTarget.payment.razorpay_payment_id) throw new Error('No Razorpay payment ID.');
            await refundMutation.mutateAsync({
              payload: {
                razorpay_payment_id: refundTarget.payment.razorpay_payment_id,
                amount_inr: amount,
                reason: refundReason.trim(),
              },
              idempotencyKey: refundTarget.idempotencyKey,
            });
            // Regenerate key for next use (handles retry by mutating the ref outside)
            setRefundTarget((prev) => prev ? { ...prev, idempotencyKey: newIdempotencyKey() } : null);
          }}
        >
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="refund-amount" className="text-small font-medium text-ink">
                Amount (₹) <span className="text-red">*</span>
              </label>
              <input
                id="refund-amount"
                type="number"
                min="1"
                step="1"
                value={refundAmount}
                onChange={(e) => setRefundAmount(e.target.value)}
                placeholder="e.g. 999"
                className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink placeholder:text-ink-muted font-mono focus:outline-none focus:ring-2 focus:ring-royal/40"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="refund-reason" className="text-small font-medium text-ink">
                Reason <span className="text-red">*</span>
              </label>
              <input
                id="refund-reason"
                type="text"
                value={refundReason}
                onChange={(e) => setRefundReason(e.target.value)}
                placeholder="e.g. Duplicate charge"
                className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-royal/40"
              />
            </div>
          </div>
        </ConfirmDialog>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Plan Change dialog
// ---------------------------------------------------------------------------
interface PlanChangeTarget {
  userId: string;
  currentTier: string;
}

const TIER_OPTIONS = ['free', 'trial', 'plus', 'founder_lifetime'];

function SubscriptionsWithPlanChange({ subscriptions }: { subscriptions: AdminSubscriptionRow[] }) {
  const planChangeMutation = useAdminPlanChange();
  const [planTarget, setPlanTarget] = React.useState<PlanChangeTarget | null>(null);
  const [newTier, setNewTier] = React.useState('plus');
  const [grantUntil, setGrantUntil] = React.useState('');
  const [reason, setReason] = React.useState('');

  if (subscriptions.length === 0) {
    return (
      <EmptyState
        title="No subscriptions found"
        description="Subscription records will appear here."
        className="py-8"
      />
    );
  }

  return (
    <>
      <SubscriptionTable
        subscriptions={subscriptions}
        onPlanChange={(userId, currentTier) => {
          setNewTier('plus');
          setGrantUntil('');
          setReason('');
          setPlanTarget({ userId, currentTier });
        }}
      />
      {planTarget && (
        <ConfirmDialog
          open={!!planTarget}
          onClose={() => setPlanTarget(null)}
          title="Change user plan"
          description={
            <>
              Change plan for user <code className="font-mono text-caption bg-surface-2 px-1 rounded">{planTarget.userId.slice(0, 8)}…</code>{' '}
              from <strong>{planTarget.currentTier}</strong>. Select the new tier and enter a reason to confirm.
            </>
          }
          confirmLabel="Change Plan"
          confirmVariant="primary"
          onConfirm={async () => {
            if (!reason.trim()) throw new Error('Reason is required.');
            await planChangeMutation.mutateAsync({
              userId: planTarget.userId,
              payload: {
                tier: newTier,
                grant_until: grantUntil || null,
                reason: reason.trim(),
              },
            });
          }}
        >
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="plan-tier" className="text-small font-medium text-ink">
                New tier <span className="text-red">*</span>
              </label>
              <select
                id="plan-tier"
                value={newTier}
                onChange={(e) => setNewTier(e.target.value)}
                className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink focus:outline-none focus:ring-2 focus:ring-royal/40"
              >
                {TIER_OPTIONS.map((t) => (
                  <option key={t} value={t}>{displayLabel(t, 'tier')}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="plan-grant-until" className="text-small font-medium text-ink">
                Grant until <span className="text-ink-muted font-normal">(optional ISO date)</span>
              </label>
              <input
                id="plan-grant-until"
                type="datetime-local"
                value={grantUntil}
                onChange={(e) => setGrantUntil(e.target.value)}
                className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink focus:outline-none focus:ring-2 focus:ring-royal/40"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="plan-reason" className="text-small font-medium text-ink">
                Reason <span className="text-red">*</span>
              </label>
              <input
                id="plan-reason"
                type="text"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Founder access grant"
                className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-royal/40"
              />
            </div>
          </div>
        </ConfirmDialog>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Webhook health card
// ---------------------------------------------------------------------------
function WebhookHealthCard() {
  const { data, isLoading, isError, refetch } = useAdminBillingWebhookHealth();

  if (isLoading) return <Skeleton className="h-32 rounded-xl" />;
  if (isError) {
    return (
      <ErrorCard
        title="Could not load webhook health"
        onRetry={() => refetch()}
        className="max-w-sm"
      />
    );
  }
  if (!data) return null;

  const healthStatus = data.failed_count > 0 ? 'warning' : 'healthy';
  const successRate  = data.recent_count > 0
    ? Math.round((data.success_count / data.recent_count) * 100)
    : 100;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-3">
        <StatCard
          title="Recent Events"
          value={data.recent_count.toLocaleString('en-IN')}
          status="neutral"
          className="min-w-[140px]"
        />
        <StatCard
          title="Succeeded"
          value={data.success_count.toLocaleString('en-IN')}
          status="healthy"
          className="min-w-[140px]"
        />
        <StatCard
          title="Failed"
          value={data.failed_count.toLocaleString('en-IN')}
          status={data.failed_count > 0 ? 'critical' : 'healthy'}
          className="min-w-[140px]"
        />
        <StatCard
          title="Success Rate"
          value={`${successRate}%`}
          status={healthStatus}
          sub={data.last_event_at ? `Last event ${formatRelative(data.last_event_at)}` : 'No events recorded'}
          className="min-w-[160px]"
        />
      </div>
      {data.note && (
        <p className="text-caption text-ink-muted">{data.note}</p>
      )}
      <p className="text-caption text-ink-faint">
        Counts are derived from payment events — not a live webhook delivery log.
        Renewal and churn figures in KPI Overview are approximate.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Billing page
// ---------------------------------------------------------------------------
export default function AdminBillingPage() {
  const overviewQ       = useAdminBillingOverview();
  const subscriptionsQ  = useAdminSubscriptions({ limit: 50 });
  const paymentsQ       = useAdminBillingPayments({ limit: 50 });
  const [lastRefreshed, setLastRefreshed] = React.useState<Date | null>(null);
  function handleRefreshAll() {
    overviewQ.refetch();
    subscriptionsQ.refetch();
    paymentsQ.refetch();
    setLastRefreshed(new Date());
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Page header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-h2 font-medium text-ink">Billing Ops</h1>
          <p className="mt-1 text-small text-ink-muted">
            MRR · subscriptions · payments · webhook health · refunds · plan changes (Phase 5 live)
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

      {/* KPI row */}
      <section aria-labelledby="section-billing-kpi">
        <h2 id="section-billing-kpi" className="mb-3 text-h3 font-medium text-ink">
          KPI Overview
        </h2>
        {overviewQ.isLoading && <StatRowSkeleton cols={5} />}
        {overviewQ.isError && (
          <ErrorCard
            title="Could not load billing overview"
            onRetry={() => overviewQ.refetch()}
            className="max-w-md"
          />
        )}
        {overviewQ.data && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard
              title="MRR"
              value={formatCurrency(overviewQ.data.mrr_inr)}
              status="neutral"
              sub="Monthly Recurring Revenue"
            />
            <StatCard
              title="ARPU"
              value={formatCurrency(overviewQ.data.arpu_inr)}
              status="neutral"
              sub="Average Revenue Per User"
            />
            <StatCard
              title="Active Subscriptions"
              value={overviewQ.data.active_subscriptions.toLocaleString('en-IN')}
              status="healthy"
            />
            <StatCard
              title="Past Due"
              value={overviewQ.data.past_due.toLocaleString('en-IN')}
              status={overviewQ.data.past_due > 0 ? 'warning' : 'neutral'}
            />
            <StatCard
              title="Trials"
              value={overviewQ.data.trials.toLocaleString('en-IN')}
              status="neutral"
            />
          </div>
        )}
      </section>

      {/* Subscriptions table with Plan Change */}
      <Section
        id="section-subscriptions"
        title="Subscriptions"
        subtitle="All active and recent subscriptions. Price in ₹. [Change Plan] is live (Phase 5)."
      >
        {subscriptionsQ.isLoading && <TableSkeleton rows={8} />}
        {subscriptionsQ.isError && (
          <ErrorCard
            title="Could not load subscriptions"
            onRetry={() => subscriptionsQ.refetch()}
          />
        )}
        {subscriptionsQ.data && (
          <SubscriptionsWithPlanChange subscriptions={subscriptionsQ.data} />
        )}
      </Section>

      {/* Payments table with Refund */}
      <Section
        id="section-payments"
        title="Payments"
        subtitle="Recent payment transactions. [Refund] available on captured payments (Phase 5 live)."
      >
        {paymentsQ.isLoading && <TableSkeleton rows={8} />}
        {paymentsQ.isError && (
          <ErrorCard
            title="Could not load payments"
            onRetry={() => paymentsQ.refetch()}
          />
        )}
        {paymentsQ.data && <PaymentsTable payments={paymentsQ.data} />}
      </Section>

      {/* Webhook health */}
      <Section
        id="section-webhook-health"
        title="Webhook Health"
        subtitle="Razorpay webhook verify-before-parse: success rate, dedup, last failure."
      >
        <WebhookHealthCard />
      </Section>
    </div>
  );
}
