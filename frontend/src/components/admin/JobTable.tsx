'use client';

import * as React from 'react';
import { HealthBadge } from './HealthBadge';
import { Button } from '@/components/ui/Button';
import { formatRelative, formatDuration } from './utils';
import { displayLabel } from '@/lib/displayLabel';
import { SortableTh, useSort, type SortAccessor } from './sortable';
import { cn } from '@/lib/cn';

export interface AdminTask {
  task_name: string;
  schedule_display: string;
  last_run_at: string | null;
  next_run_at: string | null;
  last_status: string | null;
  last_duration_s: number | null;
  last_rows: number | null;
  paused: boolean;
}

interface JobTableProps {
  jobs: AdminTask[];
  onTrigger: (name: string) => Promise<void>;
  onPause:   (name: string) => Promise<void>;
  onResume:  (name: string) => Promise<void>;
}

const HEADERS: Array<{ label: string; sortKey?: string; right?: boolean }> = [
  { label: 'Job', sortKey: 'job' },
  { label: 'Schedule' },
  { label: 'Last Run', sortKey: 'last_run' },
  { label: 'Next Run' },
  { label: 'Status', sortKey: 'status' },
  { label: 'Duration', sortKey: 'duration', right: true },
  { label: 'Rows', sortKey: 'rows', right: true },
  { label: 'Actions' },
];

const JOB_ACCESSORS: Record<string, SortAccessor<AdminTask>> = {
  job: (j) => displayLabel(j.task_name, 'task'),
  last_run: (j) => j.last_run_at,
  status: (j) => (j.paused ? 'Paused' : j.last_status),
  duration: (j) => j.last_duration_s,
  rows: (j) => j.last_rows,
};

export function JobTable({ jobs, onTrigger, onPause, onResume }: JobTableProps) {
  const [pending, setPending] = React.useState<Record<string, string>>({});
  const { sorted, sort, toggle } = useSort(jobs, JOB_ACCESSORS);

  async function handle(name: string, action: 'trigger' | 'pause' | 'resume') {
    setPending((p) => ({ ...p, [name]: action }));
    try {
      if (action === 'trigger') await onTrigger(name);
      if (action === 'pause')   await onPause(name);
      if (action === 'resume')  await onResume(name);
    } finally {
      setPending((p) => { const n = { ...p }; delete n[name]; return n; });
    }
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <caption className="sr-only">Scheduled background jobs — name, schedule, run history, and controls</caption>
        <thead>
          <tr className="border-b border-line">
            {HEADERS.map((h) => (
              <SortableTh
                key={h.label}
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
          {sorted.map((job) => {
            const humanName = displayLabel(job.task_name, 'task');

            return (
              <tr key={job.task_name} className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors">
                <td className="py-3 pr-4">
                  <p
                    className="font-medium text-ink"
                    title={job.task_name}
                  >
                    {humanName}
                  </p>
                </td>
                <td className="py-3 pr-4 text-ink-muted font-mono text-[11px]">{job.schedule_display}</td>
                <td className="py-3 pr-4 text-ink-muted font-mono text-[11px]">{formatRelative(job.last_run_at)}</td>
                <td
                  className="py-3 pr-4 text-ink-muted font-mono text-[11px]"
                  title="Next-run times are not yet computed by the backend"
                >
                  {job.next_run_at ? formatRelative(job.next_run_at) : (
                    <span className="text-ink-faint italic">Not scheduled yet</span>
                  )}
                </td>
                <td className="py-3 pr-4">
                  {job.paused ? (
                    <HealthBadge status="Paused" />
                  ) : job.last_status ? (
                    <HealthBadge
                      status={job.last_status as Parameters<typeof HealthBadge>[0]['status']}
                    />
                  ) : (
                    <span className="text-ink-faint text-caption">—</span>
                  )}
                </td>
                <td className="py-3 pr-4 text-right font-mono tabular-nums text-ink-secondary">
                  {formatDuration(job.last_duration_s)}
                </td>
                <td className="py-3 pr-4 text-right font-mono tabular-nums text-ink">
                  {job.last_rows != null ? job.last_rows.toLocaleString('en-IN') : '—'}
                </td>
                <td className="py-3">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={() => handle(job.task_name, 'trigger')}
                      disabled={!!pending[job.task_name]}
                      aria-busy={pending[job.task_name] === 'trigger'}
                    >
                      {pending[job.task_name] === 'trigger' ? '…' : 'Run Now'}
                    </Button>
                    {job.paused ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handle(job.task_name, 'resume')}
                        disabled={!!pending[job.task_name]}
                      >
                        Resume
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handle(job.task_name, 'pause')}
                        disabled={!!pending[job.task_name]}
                      >
                        Pause
                      </Button>
                    )}
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
