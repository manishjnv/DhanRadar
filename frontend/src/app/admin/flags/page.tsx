'use client';

/**
 * Admin Feature Flags — /admin/flags
 * Tier-A read-only page.
 *
 * Displays the current flag list (Name · Description · Value · Source).
 * All toggle controls are DISABLED — flags are env-driven; changes require
 * a config update and container restart (not a UI mutation).
 *
 * Four-state contract: skeleton / empty / error+retry / data.
 * No advisory verbs.
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { useAdminFlags, type AdminFlag } from '@/features/admin/api';
import { cn } from '@/lib/cn';
import { displayLabel } from '@/lib/displayLabel';
import { formatRelative } from '@/components/admin/utils';

// Per-flag help text: what on/off means in plain words.
const FLAG_HELP: Record<string, string> = {
  AUDIT_ARCHIVE_ENABLED: 'On: audit records are archived daily. Off: archiving is paused.',
  COOKIE_SECURE: 'On: session cookies require HTTPS. Off: cookies are sent over any connection (development only).',
  DPDP_CONSENT_ENFORCED: 'On: data-processing routes require active user consent. Off: consent checks are skipped.',
};

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------
function TableSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2">
      {[...Array(rows)].map((_, i) => (
        <Skeleton key={i} className="h-11 rounded-md" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Value badge — on / off pill
// ---------------------------------------------------------------------------
function ValueBadge({ value }: { value: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-caption font-medium',
        value
          ? 'bg-emerald/10 text-emerald'
          : 'bg-surface-2 text-ink-muted border border-line',
      )}
    >
      {value ? 'on' : 'off'}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Flags table
// ---------------------------------------------------------------------------
function FlagsTable({ flags }: { flags: AdminFlag[] }) {
  if (flags.length === 0) {
    return (
      <EmptyState
        title="No feature flags"
        description="Feature flag configuration will appear here once flags are defined in the running config."
        className="py-12"
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <caption className="sr-only">Feature flags from the running server config</caption>
        <thead>
          <tr className="border-b border-line">
            <th scope="col" className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">Name</th>
            <th scope="col" className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">Description</th>
            <th scope="col" className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">Value</th>
            <th scope="col" className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">Source</th>
            {/* Read-only switch column */}
            <th scope="col" className="pb-2 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {flags.map((flag) => {
            const humanName = displayLabel(flag.key, 'flag');
            const helpText = FLAG_HELP[flag.key];
            const sourceLabel = flag.source === 'env'
              ? 'Set via server config (restart to change)'
              : flag.source;
            return (
              <tr
                key={flag.key}
                className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors"
              >
                <td className="py-3 pr-4 whitespace-nowrap">
                  <span className="text-small font-medium text-ink">{humanName}</span>
                  <span
                    className="block font-mono text-[10px] text-ink-faint mt-0.5"
                    title={flag.key}
                  >
                    {flag.key}
                  </span>
                </td>
                <td className="py-3 pr-4 text-small text-ink-secondary max-w-xs">
                  <span>{flag.description || '—'}</span>
                  {helpText && (
                    <span className="block mt-0.5 text-caption text-ink-muted">{helpText}</span>
                  )}
                </td>
                <td className="py-3 pr-4">
                  <ValueBadge value={flag.value} />
                </td>
                <td className="py-3 pr-4 text-caption text-ink-muted">
                  {sourceLabel}
                </td>
                <td className="py-3">
                  {/* Always disabled — env-driven */}
                  <button
                    disabled
                    title="Set via server config — change via config file and restart the container"
                    className={cn(
                      'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
                      'cursor-not-allowed opacity-40',
                      flag.value ? 'bg-emerald/40' : 'bg-surface-2 border border-line',
                    )}
                    aria-checked={flag.value}
                    role="switch"
                    aria-disabled="true"
                  >
                    <span
                      className={cn(
                        'inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow-sm transition-transform',
                        flag.value ? 'translate-x-4' : 'translate-x-0.5',
                      )}
                    />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Flags page
// ---------------------------------------------------------------------------
export default function AdminFlagsPage() {
  const flagsQ = useAdminFlags();

  return (
    <div className="flex flex-col gap-8">
      {/* Page header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-h2 font-medium text-ink">Feature Flags</h1>
          <p className="mt-1 text-small text-ink-muted">
            Read-only view of current feature flags from the running config. Toggles are disabled —
            flags are set via server config and require a container restart to change.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {flagsQ.dataUpdatedAt > 0 && (
            <span className="text-caption text-ink-muted">
              Last updated {formatRelative(new Date(flagsQ.dataUpdatedAt).toISOString())}
            </span>
          )}
          <Button variant="ghost" size="sm" onClick={() => flagsQ.refetch()}>
            <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Info note */}
      <div className="rounded-lg border border-amber/30 bg-amber/5 px-5 py-3">
        <p className="text-small text-amber">
          These flags are read-only here and change only via server config.
        </p>
      </div>

      {/* Flags table */}
      <section aria-labelledby="section-flags-table">
        <Card>
          <CardHeader>
            <CardTitle id="section-flags-table">Flag List</CardTitle>
            <p className="mt-1 text-small text-ink-muted">
              Name · Description · Current value · Source.
            </p>
          </CardHeader>
          <CardBody>
            {flagsQ.isLoading && <TableSkeleton rows={8} />}
            {flagsQ.isError && (
              <ErrorCard
                title="Could not load feature flags"
                onRetry={() => flagsQ.refetch()}
              />
            )}
            {flagsQ.data && <FlagsTable flags={flagsQ.data} />}
          </CardBody>
        </Card>
      </section>
    </div>
  );
}
