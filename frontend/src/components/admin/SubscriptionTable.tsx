'use client';

/**
 * SubscriptionTable — compact table of billing subscription rows.
 *
 * Columns: User ID · Email · Plan · Status · Renews · Price (₹)
 * No advisory verbs. Numeric values allowed (admin-only, Admin.md §16).
 */

import * as React from 'react';
import { HealthBadge } from './HealthBadge';
import { formatDateTime, formatCurrency } from './utils';
import { cn } from '@/lib/cn';
import type { AdminSubscriptionRow } from '@/features/admin/api';

interface SubscriptionTableProps {
  subscriptions: AdminSubscriptionRow[];
}

const HEADERS = ['User ID', 'Email', 'Plan', 'Status', 'Renews', 'Price'];

function subStatusBadge(status: string): React.ReactNode {
  const map: Record<string, Parameters<typeof HealthBadge>[0]['status']> = {
    active:   'Healthy',
    past_due: 'Warning',
    trialing: 'Skipped',
    canceled: 'Paused',
    failed:   'Failed',
  };
  return <HealthBadge status={map[status] ?? 'Planned'} />;
}

export function SubscriptionTable({ subscriptions }: SubscriptionTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <thead>
          <tr className="border-b border-line">
            {HEADERS.map((h) => (
              <th
                key={h}
                className={cn(
                  'pb-2 pr-4 text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono',
                  h === 'Price' ? 'text-right' : 'text-left',
                )}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {subscriptions.map((sub, i) => (
            <tr
              key={`${sub.user_id}-${i}`}
              className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors"
            >
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                {sub.user_id.slice(0, 8)}…
              </td>
              <td className="py-2.5 pr-4 text-ink-secondary text-[11px]">
                {sub.email}
              </td>
              <td className="py-2.5 pr-4 font-medium text-ink">
                {sub.plan}
              </td>
              <td className="py-2.5 pr-4">
                {subStatusBadge(sub.status)}
              </td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                {sub.current_period_end ? formatDateTime(sub.current_period_end) : '—'}
              </td>
              <td className="py-2.5 text-right font-mono tabular-nums text-ink">
                {formatCurrency(sub.price_inr)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
