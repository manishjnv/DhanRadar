'use client';

/**
 * Admin Operations — /admin/operations
 *
 * Five sections: A) Data Sources · B) Scheduled Jobs · C) Run History · D) Data Quality · E) Platform Settings
 *
 * Four-state contract per section: Default · Loading (skeleton) · Empty · Error+Retry
 * Numeric values ARE allowed (admin-only, §16).
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
import { SourceTable } from '@/components/admin/SourceTable';
import { JobTable } from '@/components/admin/JobTable';
import { RunHistoryTable } from '@/components/admin/RunHistoryTable';
import { QualityIssueTable } from '@/components/admin/QualityIssueTable';
import { SideDrawer } from '@/components/admin/SideDrawer';
import {
  useAdminSources,
  useAdminTasks,
  useAdminRuns,
  useAdminQuality,
  useAdminRunDetail,
  useSourceSync,
  useSourcePause,
  useSourceResume,
  useTaskTrigger,
  useTaskPause,
  useTaskResume,
  useQualityAcknowledge,
} from '@/features/admin/api';
import { formatDateTime, formatDuration, formatRelative } from '@/components/admin/utils';
import { displayLabel } from '@/lib/displayLabel';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// Table skeleton
// ---------------------------------------------------------------------------
function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2">
      {[...Array(rows)].map((_, i) => (
        <Skeleton key={i} className="h-12 rounded-md" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section wrapper
// ---------------------------------------------------------------------------
function Section({
  id,
  title,
  subtitle,
  children,
}: {
  id: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={id}>
      <Card>
        <CardHeader>
          <div>
            <CardTitle id={id}>{title}</CardTitle>
            {subtitle && <p className="mt-1 text-small text-ink-muted">{subtitle}</p>}
          </div>
        </CardHeader>
        <CardBody>{children}</CardBody>
      </Card>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Run detail drawer content
// ---------------------------------------------------------------------------
function RunDetailContent({ runId }: { runId: string }) {
  const { data, isLoading, isError } = useAdminRunDetail(runId);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-8 rounded" />)}
      </div>
    );
  }

  if (isError || !data) {
    return <ErrorCard title="Could not load run detail" />;
  }

  const rows: Array<{ label: string; value: React.ReactNode }> = [
    { label: 'Run ID',         value: <span className="font-mono text-[11px]">{data.run_id}</span> },
    { label: 'Source',         value: data.source },
    { label: 'Task',           value: displayLabel(data.task_name, 'task') },
    { label: 'Status',         value: displayLabel(data.status, 'runStatus') },
    { label: 'Started',        value: formatDateTime(data.started_at) },
    { label: 'Finished',       value: formatDateTime(data.finished_at) },
    { label: 'Duration',       value: formatDuration(data.duration_s) },
    { label: 'Records written',value: data.records_written?.toLocaleString('en-IN') ?? '—' },
    { label: 'Records failed', value: data.records_failed?.toLocaleString('en-IN') ?? '—' },
    { label: 'Raw file path',  value: data.raw_file_path ?? '—' },
  ];

  return (
    <div className="flex flex-col gap-4">
      <dl className="flex flex-col gap-2">
        {rows.map(({ label, value }) => (
          <div key={label} className="flex items-start justify-between gap-4 border-b border-line py-2 last:border-0">
            <dt className="text-small text-ink-muted shrink-0 w-40">{label}</dt>
            <dd className="text-small text-ink text-right">{value}</dd>
          </div>
        ))}
      </dl>

      {data.error_detail && (
        <div className="rounded-lg bg-red/5 border border-red/20 p-4">
          <p className="text-small font-medium text-red mb-1">Error detail</p>
          <pre className="text-[11px] text-red/80 whitespace-pre-wrap break-all font-mono">
            {data.error_detail}
          </pre>
        </div>
      )}

      {data.run_metadata && Object.keys(data.run_metadata).length > 0 && (
        <div className="rounded-lg bg-surface-2 p-4">
          <p className="text-small font-medium text-ink mb-2">Run metadata</p>
          <pre className="text-[11px] text-ink-muted whitespace-pre-wrap break-all font-mono">
            {JSON.stringify(data.run_metadata, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Source log drawer content — shows recent runs filtered by source
// ---------------------------------------------------------------------------
function SourceLogsContent({ sourceKey }: { sourceKey: string }) {
  const { data, isLoading, isError } = useAdminRuns({ source: sourceKey, limit: 20 });

  if (isLoading) return <TableSkeleton rows={5} />;
  if (isError)   return <ErrorCard title="Could not load source logs" />;

  const runs = data ?? [];

  if (runs.length === 0) {
    return (
      <EmptyState
        title="No runs found"
        description={`No recent runs recorded for ${displayLabel(sourceKey)}.`}
      />
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {runs.map((run) => (
        <div
          key={run.run_id}
          className={cn(
            'rounded-lg border p-3 text-small',
            run.status === 'failed'  ? 'border-red/30 bg-red/5'  :
            run.status === 'running' ? 'border-royal/30 bg-royal/5' :
            'border-line bg-surface-2',
          )}
        >
          <div className="flex items-center justify-between gap-2">
            <span className={cn(
              'font-medium',
              run.status === 'failed'  ? 'text-red' :
              run.status === 'success' ? 'text-emerald' : 'text-ink',
            )}>
              {displayLabel(run.status, 'runStatus')}
            </span>
            <span className="font-mono text-[11px] text-ink-muted">{formatDateTime(run.started_at)}</span>
          </div>
          <div className="mt-1 flex items-center gap-3 text-caption text-ink-muted">
            <span>{formatDuration(run.duration_s)}</span>
            <span>{run.records_written?.toLocaleString('en-IN') ?? '—'} written</span>
            {run.error_class && (
              <span className="text-red" title={run.error_class}>
                {run.error_class.split('.').pop() ?? run.error_class}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Settings stub (Section E)
// ---------------------------------------------------------------------------
function SettingsStub() {
  return (
    <div className="flex flex-col gap-4 text-small text-ink-muted">
      <p>
        Platform settings (support email, notification thresholds, maintenance actions,
        admin users list) — not yet available.
      </p>
      <div className="rounded-lg border border-line bg-surface-2 p-4">
        <p className="text-caption uppercase tracking-wide font-medium text-ink-faint mb-2">Admin Users</p>
        <p className="text-small text-ink-secondary">
          Authorization is UUID-only, configured via <code className="font-mono text-[11px] bg-surface-3 px-1 rounded">ADMIN_USER_IDS</code> env var.
          Changes require a container restart — no UI mutation (protects allowlist integrity).
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Operations page
// ---------------------------------------------------------------------------
export default function AdminOperationsPage() {
  // Mutation hooks
  const sourceSync   = useSourceSync();
  const sourcePause  = useSourcePause();
  const sourceResume = useSourceResume();
  const taskTrigger  = useTaskTrigger();
  const taskPause    = useTaskPause();
  const taskResume   = useTaskResume();
  const qualityAck   = useQualityAcknowledge();

  // Queries
  const sourcesQ = useAdminSources();
  const tasksQ   = useAdminTasks();
  const runsQ    = useAdminRuns({ limit: 50 });
  const qualityQ = useAdminQuality();

  // Drawer state
  const [runDrawer, setRunDrawer]       = React.useState<string | null>(null);
  const [sourceDrawer, setSourceDrawer] = React.useState<string | null>(null);

  // Resolve source display name for drawer title
  const sourceDrawerName = React.useMemo(() => {
    if (!sourceDrawer) return '';
    const src = sourcesQ.data?.find((s) => s.source_key === sourceDrawer);
    return src?.name ?? displayLabel(sourceDrawer);
  }, [sourceDrawer, sourcesQ.data]);

  return (
    <div className="flex flex-col gap-8">
      {/* Page header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-h2 font-medium text-ink">Operations</h1>
          <p className="mt-1 text-small text-ink-muted">
            Data sources · jobs · runs · quality · settings
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              sourcesQ.refetch();
              tasksQ.refetch();
              runsQ.refetch();
              qualityQ.refetch();
            }}
          >
            <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
            Refresh all
          </Button>
          {sourcesQ.dataUpdatedAt > 0 && (
            <p className="text-caption text-ink-faint">
              Last updated {formatRelative(new Date(sourcesQ.dataUpdatedAt).toISOString())}
            </p>
          )}
        </div>
      </div>

      {/* Section A — Data Sources */}
      <Section
        id="section-sources"
        title="Data Sources"
        subtitle="External data feeds powering DhanRadar — each row shows connection tier, schedule, and the last successful sync."
      >
        {sourcesQ.isLoading && <TableSkeleton rows={6} />}
        {sourcesQ.isError && (
          <ErrorCard
            title="Could not load sources"
            onRetry={() => sourcesQ.refetch()}
          />
        )}
        {sourcesQ.data && sourcesQ.data.length === 0 && (
          <EmptyState title="No sources configured" description="Sources will appear here once the backend returns data." />
        )}
        {sourcesQ.data && sourcesQ.data.length > 0 && (
          <SourceTable
            sources={sourcesQ.data}
            onSync={async (key) => { await sourceSync.mutateAsync(key); }}
            onPause={async (key) => { await sourcePause.mutateAsync(key); }}
            onResume={async (key) => { await sourceResume.mutateAsync(key); }}
            onViewLogs={(key) => setSourceDrawer(key)}
          />
        )}
      </Section>

      {/* Section B — Scheduled Jobs */}
      <Section
        id="section-jobs"
        title="Scheduled Jobs"
        subtitle="Celery beat background tasks — each job refreshes a dataset or performs a housekeeping action on a fixed schedule."
      >
        {tasksQ.isLoading && <TableSkeleton rows={8} />}
        {tasksQ.isError && (
          <ErrorCard
            title="Could not load jobs"
            onRetry={() => tasksQ.refetch()}
          />
        )}
        {tasksQ.data && tasksQ.data.length === 0 && (
          <EmptyState title="No jobs found" />
        )}
        {tasksQ.data && tasksQ.data.length > 0 && (
          <>
            <p className="mb-3 text-caption text-ink-faint">
              Next-run times are not yet computed — schedules are active; the system runs each job at the configured interval.
            </p>
            <JobTable
              jobs={tasksQ.data}
              onTrigger={async (name) => { await taskTrigger.mutateAsync(name); }}
              onPause={async (name) => { await taskPause.mutateAsync(name); }}
              onResume={async (name) => { await taskResume.mutateAsync(name); }}
            />
          </>
        )}
      </Section>

      {/* Section C — Run History */}
      <Section
        id="section-runs"
        title="Run History"
        subtitle="The 50 most recent data ingestion runs across all sources — click a row to see the full run detail."
      >
        {runsQ.isLoading && <TableSkeleton rows={8} />}
        {runsQ.isError && (
          <ErrorCard
            title="Could not load run history"
            onRetry={() => runsQ.refetch()}
          />
        )}
        {runsQ.data && runsQ.data.length === 0 && (
          <EmptyState
            title="No runs yet"
            description="Run history will appear here after tasks have executed."
          />
        )}
        {runsQ.data && runsQ.data.length > 0 && (
          <RunHistoryTable
            runs={runsQ.data}
            onViewDetail={(id) => setRunDrawer(id)}
          />
        )}
      </Section>

      {/* Section D — Data Quality */}
      <Section
        id="section-quality"
        title="Data Quality"
        subtitle="Automated checks that compare current pipeline metrics against expected thresholds — alerts appear here when a check fails."
      >
        {qualityQ.isLoading && <TableSkeleton rows={4} />}
        {qualityQ.isError && (
          <ErrorCard
            title="Could not load quality data"
            onRetry={() => qualityQ.refetch()}
          />
        )}
        {qualityQ.data && qualityQ.data.length === 0 && (
          <EmptyState
            title="No quality evaluations yet"
            description="No quality evaluations have run yet — this is not a clean-bill confirmation."
          />
        )}
        {qualityQ.data && qualityQ.data.length > 0 && (
          <QualityIssueTable
            issues={qualityQ.data}
            onReview={(key) => {
              // Phase 2: open filtered audit table
              console.log('Review quality metric:', key);
            }}
            onAcknowledge={async (key, days) => {
              await qualityAck.mutateAsync({ metricKey: key, durationDays: days });
            }}
          />
        )}
      </Section>

      {/* Section E — Platform Settings (stub) */}
      <Section
        id="section-settings"
        title="Platform Settings"
        subtitle="Global operator configuration — admin access, notification thresholds, and maintenance controls."
      >
        <SettingsStub />
      </Section>

      {/* Run detail drawer */}
      <SideDrawer
        title="Run Detail"
        open={!!runDrawer}
        onClose={() => setRunDrawer(null)}
      >
        {runDrawer && <RunDetailContent runId={runDrawer} />}
      </SideDrawer>

      {/* Source logs drawer */}
      <SideDrawer
        title={sourceDrawerName ? `Logs — ${sourceDrawerName}` : 'Source Logs'}
        open={!!sourceDrawer}
        onClose={() => setSourceDrawer(null)}
      >
        {sourceDrawer && <SourceLogsContent sourceKey={sourceDrawer} />}
      </SideDrawer>
    </div>
  );
}
