'use client';

import * as React from 'react';
import { useSignalDeployments } from '@/features/signal/api';
import type { SignalState } from '@/features/signal/types';

const inrFmt = (n: number) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(n);

const STATE_BADGE: Record<SignalState, string> = {
  triggered: 'badge-pos',
  watch: 'badge-warn',
  no_signal: 'badge-neutral',
};

const STATE_LABEL: Record<SignalState, string> = {
  triggered: 'Triggered',
  watch: 'Watch',
  no_signal: 'No signal',
};

export function DeploymentHistory() {
  const { data: deployments, isLoading } = useSignalDeployments();

  if (isLoading) {
    return (
      <div className="card-pad animate-pulse space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-8 rounded bg-surface-2" />
        ))}
      </div>
    );
  }

  const rows = deployments ?? [];

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-surface">
      <div className="border-b border-line px-4 py-3">
        <p className="text-small font-medium text-ink">Deployment history</p>
      </div>

      {rows.length === 0 ? (
        <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
          <p className="text-small text-ink-muted">No deployments yet.</p>
          <p className="text-caption text-ink-faint">
            Your dip fund is ready when the signal triggers.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="dt">
            <thead>
              <tr>
                <th className="px-4">Date</th>
                <th className="px-4">Amount</th>
                <th className="px-4">Signal</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="mono px-4 text-ink-muted">
                    {new Date(row.date).toLocaleDateString('en-IN', {
                      day: '2-digit',
                      month: 'short',
                      year: '2-digit',
                    })}
                  </td>
                  <td className="mono px-4 text-right font-medium text-ink">
                    {row.amount != null ? inrFmt(row.amount) : '—'}
                  </td>
                  <td className="px-4">
                    {row.signal_state ? (
                      <span className={STATE_BADGE[row.signal_state as SignalState]}>
                        {STATE_LABEL[row.signal_state as SignalState]}
                      </span>
                    ) : (
                      <span className="badge-neutral">Unknown</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
