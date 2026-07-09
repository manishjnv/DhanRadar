'use client';

import * as React from 'react';
import { HealthBadge } from './HealthBadge';
import { Button } from '@/components/ui/Button';
import { formatRelative } from './utils';
import { SortableTh, useSort, type SortAccessor } from './sortable';
import { cn } from '@/lib/cn';

export interface AdminSource {
  source_key: string;
  name: string;
  tier: string;
  description: string;
  method: string;
  schedule_display: string;
  cost: string;
  last_success_at: string | null;
  last_records: number | null;
  status: string;
  paused: boolean;
}

interface SourceTableProps {
  sources: AdminSource[];
  onSync: (key: string) => Promise<void>;
  onPause: (key: string) => Promise<void>;
  onResume: (key: string) => Promise<void>;
  onViewLogs: (key: string) => void;
}

const HEADERS: Array<{ label: string; sortKey?: string; right?: boolean }> = [
  { label: 'Source', sortKey: 'name' },
  { label: 'Tier', sortKey: 'tier' },
  { label: 'Method', sortKey: 'method' },
  { label: 'Schedule' },
  { label: 'Cost', sortKey: 'cost' },
  { label: 'Last Success', sortKey: 'last_success' },
  { label: 'Records', sortKey: 'records', right: true },
  { label: 'Status', sortKey: 'status' },
  { label: 'Actions' },
];

const SOURCE_ACCESSORS: Record<string, SortAccessor<AdminSource>> = {
  name: (s) => s.name,
  tier: (s) => s.tier,
  method: (s) => s.method,
  cost: (s) => s.cost,
  last_success: (s) => s.last_success_at,
  records: (s) => s.last_records,
  status: (s) => (s.paused ? 'Paused' : s.status),
};

export function SourceTable({ sources, onSync, onPause, onResume, onViewLogs }: SourceTableProps) {
  const [pending, setPending] = React.useState<Record<string, string>>({});
  const { sorted, sort, toggle } = useSort(sources, SOURCE_ACCESSORS);

  async function handle(key: string, action: 'sync' | 'pause' | 'resume') {
    setPending((p) => ({ ...p, [key]: action }));
    try {
      if (action === 'sync')   await onSync(key);
      if (action === 'pause')  await onPause(key);
      if (action === 'resume') await onResume(key);
    } finally {
      setPending((p) => { const n = { ...p }; delete n[key]; return n; });
    }
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <caption className="sr-only">Data sources — ingestion tier, schedule, last successful run, and controls</caption>
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
          {sorted.map((src) => (
            <tr key={src.source_key} className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors">
              <td className="py-3 pr-4">
                <p className="font-medium text-ink">{src.name}</p>
                <p className="text-caption text-ink-muted mt-0.5">{src.description}</p>
              </td>
              <td className="py-3 pr-4 text-ink-secondary font-mono">{src.tier}</td>
              <td className="py-3 pr-4 text-ink-secondary">{src.method}</td>
              <td className="py-3 pr-4 text-ink-secondary font-mono text-[11px]">{src.schedule_display}</td>
              <td className="py-3 pr-4 text-ink-secondary">{src.cost}</td>
              <td className="py-3 pr-4 text-ink-muted font-mono text-[11px]">{formatRelative(src.last_success_at)}</td>
              <td className="py-3 pr-4 text-right font-mono tabular-nums text-ink">
                {src.last_records != null ? src.last_records.toLocaleString('en-IN') : '—'}
              </td>
              <td className="py-3 pr-4">
                <HealthBadge status={(src.paused ? 'Paused' : src.status) as Parameters<typeof HealthBadge>[0]['status']} />
              </td>
              <td className="py-3">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => handle(src.source_key, 'sync')}
                    disabled={!!pending[src.source_key] || src.status === 'Planned'}
                    aria-busy={pending[src.source_key] === 'sync'}
                  >
                    {pending[src.source_key] === 'sync' ? '…' : 'Sync Now'}
                  </Button>
                  {src.paused ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handle(src.source_key, 'resume')}
                      disabled={!!pending[src.source_key]}
                      aria-busy={pending[src.source_key] === 'resume'}
                    >
                      Resume
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handle(src.source_key, 'pause')}
                      disabled={!!pending[src.source_key]}
                      aria-busy={pending[src.source_key] === 'pause'}
                    >
                      Pause
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onViewLogs(src.source_key)}
                  >
                    View Logs
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
