'use client';

import * as React from 'react';
import { HealthBadge } from './HealthBadge';
import { Button } from '@/components/ui/Button';
import { formatRelative, formatDuration } from './utils';
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

export function JobTable({ jobs, onTrigger, onPause, onResume }: JobTableProps) {
  const [pending, setPending] = React.useState<Record<string, string>>({});

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
        <thead>
          <tr className="border-b border-line">
            {['Job', 'Schedule', 'Last Run', 'Next Run', 'Status', 'Duration', 'Rows', 'Actions'].map((h) => (
              <th
                key={h}
                className={cn(
                  'pb-2 pr-4 text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono',
                  h === 'Duration' || h === 'Rows' ? 'text-right' : 'text-left',
                )}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.task_name} className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors">
              <td className="py-3 pr-4 font-medium text-ink font-mono text-[12px]">{job.task_name}</td>
              <td className="py-3 pr-4 text-ink-muted font-mono text-[11px]">{job.schedule_display}</td>
              <td className="py-3 pr-4 text-ink-muted font-mono text-[11px]">{formatRelative(job.last_run_at)}</td>
              <td className="py-3 pr-4 text-ink-muted font-mono text-[11px]">{formatRelative(job.next_run_at)}</td>
              <td className="py-3 pr-4">
                {job.paused
                  ? <HealthBadge status="Paused" />
                  : job.last_status
                    ? <HealthBadge status={job.last_status as Parameters<typeof HealthBadge>[0]['status']} />
                    : <span className="text-ink-faint text-caption">—</span>
                }
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
          ))}
        </tbody>
      </table>
    </div>
  );
}
