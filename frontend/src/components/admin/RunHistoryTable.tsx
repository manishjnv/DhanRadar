'use client';

import * as React from 'react';
import { HealthBadge } from './HealthBadge';
import { Button } from '@/components/ui/Button';
import { formatRelative, formatDuration } from './utils';
import { displayLabel, titleCase } from '@/lib/displayLabel';
import { SortableTh, useSort, type SortAccessor } from './sortable';
import { cn } from '@/lib/cn';

export interface AdminRun {
  run_id: number;
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

const HEADERS: Array<{ label: string; sortKey?: string; right?: boolean }> = [
  { label: 'Run', sortKey: 'run_id' },
  { label: 'Source', sortKey: 'source' },
  { label: 'Started', sortKey: 'started' },
  { label: 'Duration', sortKey: 'duration', right: true },
  { label: 'Records OK', sortKey: 'ok', right: true },
  { label: 'Records Failed', sortKey: 'failed', right: true },
  { label: 'Status', sortKey: 'status' },
  { label: '' },
];

const RUN_ACCESSORS: Record<string, SortAccessor<AdminRun>> = {
  run_id: (r) => r.run_id,
  source: (r) => displayLabel(r.source, 'source'),
  started: (r) => r.started_at,
  duration: (r) => r.duration_s,
  ok: (r) => r.records_written,
  failed: (r) => r.records_failed,
  status: (r) => r.status,
};

export function RunHistoryTable({ runs, onViewDetail }: RunHistoryTableProps) {
  const { sorted, sort, toggle } = useSort(runs, RUN_ACCESSORS);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <caption className="sr-only">Recent ingestion run history — status, duration, and record counts per run</caption>
        <thead>
          <tr className="border-b border-line">
            {HEADERS.map((h) => (
              <SortableTh
                key={h.label || 'actions'}
                label={h.label}
                sortKey={h.sortKey}
                sort={sort}
                onToggle={toggle}
                className={cn(h.right && 'text-right')}
              />
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((run) => {
            // Friendly error_class text — raw Python class names surfaced via title tooltip.
            const errorText = run.error_class
              ? titleCase(run.error_class.split('.').pop() ?? run.error_class)
              : null;

            return (
              <tr
                key={run.run_id}
                className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors cursor-pointer"
                onClick={() => onViewDetail(String(run.run_id))}
              >
                <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                  #{run.run_id}
                </td>
                <td className="py-2.5 pr-4 text-ink font-medium" title={run.source}>
                  {displayLabel(run.source, 'source')}
                </td>
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
                  <div className="flex flex-col items-start gap-0.5">
                    <HealthBadge status={run.status as Parameters<typeof HealthBadge>[0]['status']} />
                    {run.error_class && (
                      <span
                        className="text-[11px] text-red/80"
                        title={run.error_class}
                      >
                        {errorText}
                      </span>
                    )}
                  </div>
                </td>
                <td className="py-2.5" onClick={(e) => e.stopPropagation()}>
                  <Button size="sm" variant="ghost" onClick={() => onViewDetail(String(run.run_id))}>
                    Detail
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
