'use client';

/**
 * Admin Billing Ops — /admin/billing
 *
 * KPI row: MRR · ARPU · Active Subs · Past Due · Trials
 * Subscriptions table: user_id · email · plan · status · renews · price (₹)
 * Payments table: user_id · razorpay_payment_id · status · ts · request_id
 * Webhook health card: success/failed counts + last_event_at
 *
 * Four-state contract per section: Default · Loading (skeleton) · Empty · Error+Retry
 * Numeric values ARE allowed (admin-only, Admin.md §16).
 * Refunds & plan changes are Phase 5 gated mutations — disabled affordance shown.
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
import { formatRelative, formatDateTime, formatCurrency } from '@/components/admin/utils';
import {
  useAdminBillingOverview,
  useAdminSubscriptions,
  useAdminBillingPayments,
  useAdminBillingWebhookHealth,
  type AdminPaymentRow,
} from '@/features/admin/api';
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
// Section wrapper
// ---------------------------------------------------------------------------
function Section({
  id,
  title,
  subtitle,
  children,
}: {
  id: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={id}>
      <Card>
        <CardHeader>
          <CardTitle id={id}>{title}</CardTitle>
          {subtitle && <p className="mt-1 text-small text-ink-muted">{subtitle}</p>}
        </CardHeader>
        <CardBody>{children}</CardBody>
      </Card>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Payments table (inline — not extracted to component since it's billing-specific)
// ---------------------------------------------------------------------------
function PaymentsTable({ payments }: { payments: AdminPaymentRow[] }) {
  if (payments.length === 0) {
    return (
      <EmptyState
        title="No payments found"
        description="Recent payments will appear here."
        className="py-8"
      />
    );
  }

  const HEADERS = ['User ID', 'Razorpay ID', 'Status', 'Timestamp', 'Request ID'];

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
                <HealthBadge
                  status={
                    p.status === 'captured' ? 'Success' :
                    p.status === 'failed'   ? 'Failed'  :
                    p.status === 'pending'  ? 'Running' :
                    'Paused'
                  }
                />
              </td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                {formatDateTime(p.ts)}
              </td>
              <td className="py-2.5 font-mono text-[11px] text-ink-muted">
                {p.request_id ? p.request_id.slice(0, 8) + '…' : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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

  const healthStatus = data.failed > 0 ? 'warning' : 'healthy';
  const successRate  = data.recent_events > 0
    ? Math.round((data.success / data.recent_events) * 100)
    : 100;

  return (
    <div className="flex flex-wrap gap-3">
      <StatCard
        title="Recent Events"
        value={data.recent_events.toLocaleString('en-IN')}
        status="neutral"
        className="min-w-[140px]"
      />
      <StatCard
        title="Succeeded"
        value={data.success.toLocaleString('en-IN')}
        status="healthy"
        className="min-w-[140px]"
      />
      <StatCard
        title="Failed"
        value={data.failed.toLocaleString('en-IN')}
        status={data.failed > 0 ? 'critical' : 'healthy'}
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
  );
}

// ---------------------------------------------------------------------------
// Billing page
// ---------------------------------------------------------------------------
export default function AdminBillingPage() {
  const overviewQ       = useAdminBillingOverview();
  const subscriptionsQ  = useAdminSubscriptions({ limit: 50 });
  const paymentsQ       = useAdminBillingPayments({ limit: 50 });

  return (
    <div className="flex flex-col gap-8">
      {/* Page header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-h2 font-medium text-ink">Billing Ops</h1>
          <p className="mt-1 text-small text-ink-muted">
            MRR · subscriptions · payments · webhook health
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            disabled
            title="Phase 5 — gated mutation"
            className="opacity-40 cursor-not-allowed"
          >
            Refunds &amp; plan changes — Phase 5
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              overviewQ.refetch();
              subscriptionsQ.refetch();
              paymentsQ.refetch();
            }}
          >
            <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
            Refresh all
          </Button>
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
            />
            <StatCard
              title="ARPU"
              value={formatCurrency(overviewQ.data.arpu_inr)}
              status="neutral"
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

      {/* Subscriptions table */}
      <Section
        id="section-subscriptions"
        title="Subscriptions"
        subtitle="All active and recent subscriptions. Price in ₹."
      >
        {subscriptionsQ.isLoading && <TableSkeleton rows={8} />}
        {subscriptionsQ.isError && (
          <ErrorCard
            title="Could not load subscriptions"
            onRetry={() => subscriptionsQ.refetch()}
          />
        )}
        {subscriptionsQ.data && subscriptionsQ.data.length === 0 && (
          <EmptyState
            title="No subscriptions found"
            description="Subscription records will appear here."
            className="py-8"
          />
        )}
        {subscriptionsQ.data && subscriptionsQ.data.length > 0 && (
          <SubscriptionTable subscriptions={subscriptionsQ.data} />
        )}
      </Section>

      {/* Payments table */}
      <Section
        id="section-payments"
        title="Payments"
        subtitle="Recent payment transactions. Refund actions available in Phase 5."
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
