'use client';

import * as React from 'react';
import { HealthBadge } from './HealthBadge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
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
  /** Optional — when omitted, no Review button renders (nothing to open yet). */
  onReview?: (key: string) => void;
  onAcknowledge: (key: string, durationDays: number) => Promise<void>;
}

const HEADERS = ['Metric', 'Current Value', 'Threshold', 'Status', 'Actions'];

export function QualityIssueTable({ issues, onReview, onAcknowledge }: QualityIssueTableProps) {
  const [pending, setPending] = React.useState<Record<string, boolean>>({});
  // snoozeTarget holds the metric_key of the issue being snoozed
  const [snoozeTarget, setSnoozeTarget] = React.useState<string | null>(null);

  async function handleAck(key: string) {
    setPending((p) => ({ ...p, [key]: true }));
    try {
      await onAcknowledge(key, 30);
    } finally {
      setPending((p) => { const n = { ...p }; delete n[key]; return n; });
    }
  }

  const snoozeIssue = snoozeTarget ? issues.find((i) => i.metric_key === snoozeTarget) : null;

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-small">
          <caption className="sr-only">Data quality checks — current value vs threshold with snooze controls</caption>
          <thead>
            <tr className="border-b border-line">
              {HEADERS.map((h) => (
                <th
                  key={h}
                  scope="col"
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
                        Snoozed until {new Date(issue.acknowledged_until!).toLocaleDateString('en-IN')}
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
                      {onReview && (
                        <Button size="sm" variant="ghost" onClick={() => onReview(issue.metric_key)}>
                          Review
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setSnoozeTarget(issue.metric_key)}
                        disabled={pending[issue.metric_key] || isAcknowledged}
                        aria-busy={pending[issue.metric_key]}
                      >
                        {pending[issue.metric_key] ? '…' : 'Snooze 30 days'}
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Snooze confirm dialog */}
      <ConfirmDialog
        open={snoozeTarget !== null}
        onClose={() => setSnoozeTarget(null)}
        title="Snooze quality alert"
        description={
          snoozeIssue
            ? <>Snooze the <strong>{snoozeIssue.label}</strong> alert for 30 days? The underlying issue will remain — snoozed alerts still appear in the table.</>
            : 'Snooze this quality alert for 30 days?'
        }
        confirmLabel="Snooze 30 days"
        onConfirm={async () => {
          if (snoozeTarget) await handleAck(snoozeTarget);
          setSnoozeTarget(null);
        }}
      />
    </>
  );
}
