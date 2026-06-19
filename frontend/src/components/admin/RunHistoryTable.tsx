'use client';

import * as React from 'react';
import { HealthBadge } from './HealthBadge';
import { Button } from '@/components/ui/Button';
import { formatRelative, formatDuration } from './utils';
import { cn } from '@/lib/cn';

export interface AdminRun {
  run_id: string;
  source: string;
  task_name: string;
  started_at: string;
  finished_at: string | null;
  duration_s: number | null;
  records_written: number | null;
  records_failed: number | null;
  status: string;
  error_class: string | null;
}

interface RunHistoryTableProps {
  runs: AdminRun[];
  onViewDetail: (runId: string) => void;
}

export function RunHistoryTable({ runs, onViewDetail }: RunHistoryTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <thead>
          <tr className="border-b border-line">
            {['Run ID', 'Source', 'Started', 'Duration', 'Records OK', 'Records Failed', 'Status', ''].map((h) => (
              <th
                key={h}
                className={cn(
                  'pb-2 pr-4 text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono',
                  h === 'Records OK' || h === 'Records Failed' || h === 'Duration'
                    ? 'text-right'
                    : 'text-left',
                )}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr
              key={run.run_id}
              className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors cursor-pointer"
              onClick={() => onViewDetail(run.run_id)}
            >
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                {run.run_id.slice(0, 8)}…
              </td>
              <td className="py-2.5 pr-4 text-ink font-medium">{run.source}</td>
              <td className="py-2.5 pr-4 text-ink-muted font-mono text-[11px]">{formatRelative(run.started_at)}</td>
              <td className="py-2.5 pr-4 text-right font-mono tabular-nums text-ink-secondary">
                {formatDuration(run.duration_s)}
              </td>
              <td className="py-2.5 pr-4 text-right font-mono tabular-nums text-ink">
                {run.records_written != null ? run.records_written.toLocaleString('en-IN') : '—'}
              </td>
              <td className="py-2.5 pr-4 text-right font-mono tabular-nums">
                <span className={run.records_failed ? 'text-red' : 'text-ink-muted'}>
                  {run.records_failed != null ? run.records_failed.toLocaleString('en-IN') : '—'}
                </span>
              </td>
              <td className="py-2.5 pr-4">
                <HealthBadge status={run.status as Parameters<typeof HealthBadge>[0]['status']} />
              </td>
              <td className="py-2.5" onClick={(e) => e.stopPropagation()}>
                <Button size="sm" variant="ghost" onClick={() => onViewDetail(run.run_id)}>
                  Detail
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
