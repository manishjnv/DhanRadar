'use client';

/**
 * SubscriptionTable — compact table of billing subscription rows.
 *
 * Columns: Email · Plan · Status · Renews · Price (₹) — sortable.
 * The raw user UUID stays available as a tooltip on the email cell.
 * No advisory verbs. Numeric values allowed (admin-only, Admin.md §16).
 */

import * as React from 'react';
import { HealthBadge } from './HealthBadge';
import { Button } from '@/components/ui/Button';
import { formatDateTime, formatCurrency } from './utils';
import { displayLabel } from '@/lib/displayLabel';
import { SortableTh, useSort, type SortAccessor } from './sortable';
import { cn } from '@/lib/cn';
import type { AdminSubscriptionRow } from '@/features/admin/api';

interface SubscriptionTableProps {
  subscriptions: AdminSubscriptionRow[];
  /** When provided, renders a [Change Plan] button per row. */
  onPlanChange?: (userId: string, currentTier: string, email: string) => void;
}

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

const SUB_ACCESSORS: Record<string, SortAccessor<AdminSubscriptionRow>> = {
  email: (s) => s.email,
  plan: (s) => displayLabel(s.plan, 'tier'),
  status: (s) => displayLabel(s.status, 'subscription'),
  renews: (s) => s.current_period_end,
  price: (s) => s.price_inr,
};

export function SubscriptionTable({ subscriptions, onPlanChange }: SubscriptionTableProps) {
  const { sorted, sort, toggle } = useSort(subscriptions, SUB_ACCESSORS);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <caption className="sr-only">Active and recent subscriptions</caption>
        <thead>
          <tr className="border-b border-line">
            <SortableTh label="User" sortKey="email" sort={sort} onToggle={toggle} />
            <SortableTh label="Plan" sortKey="plan" sort={sort} onToggle={toggle} />
            <SortableTh label="Status" sortKey="status" sort={sort} onToggle={toggle} />
            <SortableTh label="Renews" sortKey="renews" sort={sort} onToggle={toggle} />
            <SortableTh label="Price" sortKey="price" sort={sort} onToggle={toggle} className={cn('text-right')} />
            {onPlanChange && <SortableTh label="" sort={sort} onToggle={toggle} />}
          </tr>
        </thead>
        <tbody>
          {sorted.map((sub, i) => (
            <tr
              key={`${sub.user_id}-${i}`}
              className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors"
            >
              <td
                className="py-2.5 pr-4 text-ink"
                title={sub.user_id ? `User ID: ${sub.user_id}` : undefined}
              >
                {sub.email}
              </td>
              <td className="py-2.5 pr-4 font-medium text-ink">
                {displayLabel(sub.plan, 'tier')}
              </td>
              <td className="py-2.5 pr-4">
                {subStatusBadge(sub.status)}
                <span className="ml-1.5 text-[11px] text-ink-secondary">
                  {displayLabel(sub.status, 'subscription')}
                </span>
              </td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                {sub.current_period_end ? formatDateTime(sub.current_period_end) : '—'}
              </td>
              <td className="py-2.5 pr-4 text-right font-mono tabular-nums text-ink">
                {formatCurrency(sub.price_inr)}
              </td>
              {onPlanChange && (
                <td className="py-2.5">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onPlanChange(sub.user_id, sub.plan, sub.email)}
                  >
                    Change Plan
                  </Button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
