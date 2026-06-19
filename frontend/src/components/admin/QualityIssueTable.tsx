'use client';

import * as React from 'react';
import { HealthBadge } from './HealthBadge';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';

export interface AdminQualityIssue {
  metric_key: string;
  label: string;
  current_value: number | null;
  threshold: number | null;
  unit: string;
  status: 'ok' | 'warning' | 'critical';
  acknowledged_until: string | null;
}

interface QualityIssueTableProps {
  issues: AdminQualityIssue[];
  onReview: (key: string) => void;
  onAcknowledge: (key: string, durationDays: number) => Promise<void>;
}

export function QualityIssueTable({ issues, onReview, onAcknowledge }: QualityIssueTableProps) {
  const [pending, setPending] = React.useState<Record<string, boolean>>({});

  async function handleAck(key: string) {
    setPending((p) => ({ ...p, [key]: true }));
    try {
      await onAcknowledge(key, 30);
    } finally {
      setPending((p) => { const n = { ...p }; delete n[key]; return n; });
    }
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <thead>
          <tr className="border-b border-line">
            {['Metric', 'Current Value', 'Threshold', 'Status', 'Actions'].map((h) => (
              <th
                key={h}
                className={cn(
                  'pb-2 pr-4 text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono',
                  h === 'Current Value' || h === 'Threshold' ? 'text-right' : 'text-left',
                )}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {issues.map((issue) => {
            const isAcknowledged =
              issue.acknowledged_until != null &&
              new Date(issue.acknowledged_until) > new Date();

            return (
              <tr key={issue.metric_key} className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors">
                <td className="py-3 pr-4">
                  <p className="font-medium text-ink">{issue.label}</p>
                  {isAcknowledged && (
                    <p className="text-caption text-amber mt-0.5">
                      Acknowledged until {new Date(issue.acknowledged_until!).toLocaleDateString('en-IN')}
                    </p>
                  )}
                </td>
                <td className="py-3 pr-4 text-right font-mono tabular-nums text-ink">
                  {issue.current_value != null
                    ? `${issue.current_value.toLocaleString('en-IN')} ${issue.unit ?? ''}`
                    : '—'}
                </td>
                <td className="py-3 pr-4 text-right font-mono tabular-nums text-ink-muted">
                  {issue.threshold != null
                    ? `${issue.threshold.toLocaleString('en-IN')} ${issue.unit ?? ''}`
                    : '—'}
                </td>
                <td className="py-3 pr-4">
                  <HealthBadge status={issue.status} />
                </td>
                <td className="py-3">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <Button size="sm" variant="ghost" onClick={() => onReview(issue.metric_key)}>
                      Review
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleAck(issue.metric_key)}
                      disabled={pending[issue.metric_key] || isAcknowledged}
                      aria-busy={pending[issue.metric_key]}
                    >
                      {pending[issue.metric_key] ? '…' : 'Ignore 30d'}
                    </Button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
