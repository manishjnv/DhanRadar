'use client';

/**
 * Admin Score Model — /admin/scoring
 * Tier-C (Admin.md §14 + §16).
 *
 * Sections:
 *   A — Active model card (version · activated/provisional badge · created_by · methodology link)
 *   B — Axis weights labeled-bar list (numerics allowed, admin-only §16)
 *   C — Coverage (total_funds)
 *   D — Registry versions table (version · created_by · approved_by · two_person_ok · activated · activated_at)
 *        Per row: non-activated rows show an Activate button that opens a confirmation dialog.
 *
 * Activate Version mutation (POST /admin/scoring/{version}/activate) is wired per-row.
 *   Requires a "backtest passed" checkbox + type-to-confirm the version string.
 *
 * Four-state contract: skeleton / empty / error+retry / data on every region.
 * No advisory verbs. No numeric in DOM on public surfaces — admin is exempt (§16).
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { RefreshCw, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { StatCard } from '@/components/admin/StatCard';
import { HealthBadge } from '@/components/admin/HealthBadge';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { formatDateTime, formatRelative } from '@/components/admin/utils';
import { SortableTh, useSort, type SortAccessor } from '@/components/admin/sortable';
import { displayLabel, personLabel } from '@/lib/displayLabel';
import {
  useAdminScoringModel,
  useAdminActivateScoringVersion,
  type AdminScoringRegistryVersion,
} from '@/features/admin/api';
import { ApiError } from '@/lib/apiClient';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function scoringActivateErrorHint(err: unknown): string {
  if (err instanceof ApiError) {
    const slug = err.problem.detail ?? '';
    if (slug === 'two_person_gate_failed') {
      return 'Two-person gate failed — the approving user must be different from the version creator.';
    }
    if (slug === 'backtest_not_passed') {
      return 'Activation rejected: the backtest must be marked as passed before activating.';
    }
    return err.problem.detail ?? err.problem.title ?? 'Activation failed. Please retry.';
  }
  if (err instanceof Error) return err.message;
  return 'Activation failed. Please retry.';
}

// ---------------------------------------------------------------------------
// Skeletons
// ---------------------------------------------------------------------------
function CardSkeleton() {
  return <Skeleton className="h-36 rounded-lg" />;
}

function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2">
      {[...Array(rows)].map((_, i) => (
        <Skeleton key={i} className="h-10 rounded-md" />
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
          <CardTitle id={id}>{title}</CardTitle>
          {subtitle && <p className="mt-1 text-small text-ink-muted">{subtitle}</p>}
        </CardHeader>
        <CardBody>{children}</CardBody>
      </Card>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Axis weights bar list
// ---------------------------------------------------------------------------
function AxisWeightBars({ weights }: { weights: Record<string, number> }) {
  const entries = Object.entries(weights).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) {
    return (
      <EmptyState
        title="No axis weights"
        description="Axis weights are not set on the active model version."
        className="py-6"
      />
    );
  }
  const maxWeight = Math.max(...entries.map(([, v]) => v));
  return (
    <div className="flex flex-col gap-3">
      {entries.map(([key, value]) => {
        const pct = maxWeight > 0 ? Math.round((value / maxWeight) * 100) : 0;
        return (
          <div key={key} className="flex items-center gap-3">
            <span className="w-40 shrink-0 text-small text-ink-muted truncate">{displayLabel(key)}</span>
            <div className="flex-1 h-2 rounded-full bg-surface-2 overflow-hidden">
              <div
                className="h-full rounded-full bg-royal/70"
                style={{ width: `${pct}%` }}
                aria-label={`${key}: ${value}`}
              />
            </div>
            <span className="w-14 text-right font-mono text-[11px] tabular-nums text-ink">
              {value}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Registry versions table
// ---------------------------------------------------------------------------
const REGISTRY_ACCESSORS: Record<string, SortAccessor<AdminScoringRegistryVersion>> = {
  version: (v) => v.model_version,
  created_by: (v) => v.created_by_email ?? v.created_by,
  approved_by: (v) => v.approved_by_email ?? v.approved_by,
  two_person: (v) => (v.two_person_ok ? 1 : 0),
  active: (v) => (v.activated ? 1 : 0),
  activated_at: (v) => v.activated_at,
  created_at: (v) => v.created_at,
};

function RegistryTable({ versions }: { versions: AdminScoringRegistryVersion[] }) {
  const [activateTarget, setActivateTarget] = React.useState<string | null>(null);
  const [backtestPassed, setBacktestPassed] = React.useState(false);
  const activateMutation = useAdminActivateScoringVersion();
  const { sorted, sort, toggle } = useSort(versions, REGISTRY_ACCESSORS);

  if (versions.length === 0) {
    return (
      <EmptyState
        title="No scoring versions yet"
        description="Each registered scoring-model version will appear here."
        className="py-8"
      />
    );
  }

  const HEADERS: Array<{ label: string; sortKey?: string }> = [
    { label: 'Version', sortKey: 'version' },
    { label: 'Created by', sortKey: 'created_by' },
    { label: 'Approved by', sortKey: 'approved_by' },
    { label: 'Approved by Two People', sortKey: 'two_person' },
    { label: 'Active', sortKey: 'active' },
    { label: 'Activated at', sortKey: 'activated_at' },
    { label: 'Created at', sortKey: 'created_at' },
    { label: 'Activate' },
  ];

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-small">
          <caption className="sr-only">Score model registry versions</caption>
          <thead>
            <tr className="border-b border-line">
              {HEADERS.map((h) => (
                <SortableTh
                  key={h.label}
                  label={h.label}
                  sortKey={h.sortKey}
                  sort={sort}
                  onToggle={toggle}
                />
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((v) => (
              <tr
                key={v.model_version}
                className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors"
              >
                <td className="py-2.5 pr-4 font-mono text-[11px] font-medium text-ink whitespace-nowrap">
                  {v.model_version}
                </td>
                <td className="py-2.5 pr-4 text-[11px] text-ink-muted" title={`Recorded as: ${v.created_by}`}>
                  {personLabel(v.created_by, v.created_by_email)}
                </td>
                <td className="py-2.5 pr-4 text-[11px] text-ink-muted" title={v.approved_by ? `Recorded as: ${v.approved_by}` : undefined}>
                  {personLabel(v.approved_by, v.approved_by_email)}
                </td>
                <td className="py-2.5 pr-4">
                  <span title="Whether a second reviewer approved this scoring version (separate from who created it).">
                    <HealthBadge status={v.two_person_ok ? 'Success' : 'Warning'} />
                  </span>
                </td>
                <td className="py-2.5 pr-4">
                  <HealthBadge status={v.activated ? 'Healthy' : 'Paused'} />
                </td>
                <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                  {formatDateTime(v.activated_at)}
                </td>
                <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                  {formatDateTime(v.created_at)}
                </td>
                <td className="py-2.5">
                  {v.activated ? (
                    <span className="text-caption text-ink-faint">active</span>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setBacktestPassed(false);
                        setActivateTarget(v.model_version);
                      }}
                    >
                      Activate
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        open={activateTarget !== null}
        onClose={() => setActivateTarget(null)}
        title="Activate scoring version"
        description={
          <>
            You are about to activate scoring version{' '}
            <strong className="font-mono">{activateTarget}</strong>. This will replace the
            currently active model and immediately affect all scored funds.
          </>
        }
        confirmLabel="Activate"
        confirmVariant="danger"
        confirmPhrase={activateTarget ?? undefined}
        onConfirm={async () => {
          if (!backtestPassed) {
            throw new Error('You must confirm the backtest has passed before activating.');
          }
          try {
            await activateMutation.mutateAsync({
              version: activateTarget!,
              payload: { backtest_passed: backtestPassed },
            });
          } catch (err) {
            throw new Error(scoringActivateErrorHint(err));
          }
        }}
      >
        {/* Backtest confirmation checkbox */}
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={backtestPassed}
            onChange={(e) => setBacktestPassed(e.target.checked)}
            className="h-4 w-4 rounded border-line accent-royal"
          />
          <span className="text-small text-ink">
            I confirm the backtest for this version has passed.
          </span>
        </label>
      </ConfirmDialog>
    </>
  );
}

// ---------------------------------------------------------------------------
// Score Model page
// ---------------------------------------------------------------------------
export default function AdminScoringPage() {
  const modelQ = useAdminScoringModel();

  return (
    <div className="flex flex-col gap-8">
      {/* Page header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-h2 font-medium text-ink">Score Model</h1>
          <p className="mt-1 text-small text-ink-muted">
            Active ranking model, axis weights, coverage, and registry.
            Activate a version per row in the registry table below.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {modelQ.dataUpdatedAt > 0 && (
            <span className="text-caption text-ink-muted">
              Last updated {formatRelative(new Date(modelQ.dataUpdatedAt).toISOString())}
            </span>
          )}
          <Button variant="ghost" size="sm" onClick={() => modelQ.refetch()}>
            <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Section A — Active model card */}
      <section aria-labelledby="section-active-model">
        <h2 id="section-active-model" className="mb-3 text-h3 font-medium text-ink">
          Active Model
        </h2>
        {modelQ.isLoading && <CardSkeleton />}
        {modelQ.isError && (
          <ErrorCard
            title="Could not load scoring model"
            onRetry={() => modelQ.refetch()}
            className="max-w-md"
          />
        )}
        {modelQ.data && (
          <Card className="p-6">
            <div className="flex flex-wrap gap-6">
              <div className="flex flex-col gap-1.5 min-w-[180px]">
                <span className="text-caption uppercase tracking-wide text-ink-muted">Version</span>
                <span className="font-mono text-h2 font-medium tabular-nums text-ink">
                  {modelQ.data.model_version}
                </span>
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="text-caption uppercase tracking-wide text-ink-muted">Status</span>
                <div className="flex items-center gap-2">
                  <HealthBadge status={modelQ.data.activated ? 'Healthy' : 'Paused'} />
                  {modelQ.data.provisional && (
                    <span title="Active, but the two-person approval has not been recorded yet.">
                      <HealthBadge status="Warning" />
                    </span>
                  )}
                  {modelQ.data.provisional && (
                    <span
                      className="text-small text-amber"
                      title="Active, but the two-person approval has not been recorded yet."
                    >
                      Provisional
                    </span>
                  )}
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="text-caption uppercase tracking-wide text-ink-muted">Created by</span>
                <span
                  className="text-small text-ink"
                  title={`Recorded as: ${modelQ.data.created_by}`}
                >
                  {personLabel(modelQ.data.created_by, modelQ.data.created_by_email)}
                </span>
              </div>
              {modelQ.data.methodology_url && (
                <div className="flex flex-col gap-1.5">
                  <span className="text-caption uppercase tracking-wide text-ink-muted">Methodology</span>
                  <a
                    href={modelQ.data.methodology_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-small text-royal hover:underline"
                  >
                    View methodology
                    <ExternalLink size={12} strokeWidth={2} aria-hidden="true" />
                  </a>
                </div>
              )}
            </div>
          </Card>
        )}
      </section>

      {/* Section B — Axis weights */}
      <Section
        id="section-axis-weights"
        title="Axis Weights"
        subtitle="Internal model weights (admin-only view). Not exposed on the public product surface."
      >
        {modelQ.isLoading && <Skeleton className="h-48 rounded-md" />}
        {modelQ.isError && (
          <ErrorCard title="Could not load axis weights" onRetry={() => modelQ.refetch()} />
        )}
        {modelQ.data && Object.keys(modelQ.data.axis_weights).length === 0 && (
          <EmptyState
            title="No axis weights configured"
            description="Weights will appear once a model version is active."
            className="py-8"
          />
        )}
        {modelQ.data && Object.keys(modelQ.data.axis_weights).length > 0 && (
          <AxisWeightBars weights={modelQ.data.axis_weights} />
        )}
      </Section>

      {/* Section C — Coverage */}
      <section aria-labelledby="section-coverage">
        <h2 id="section-coverage" className="mb-3 text-h3 font-medium text-ink">
          Coverage
        </h2>
        {modelQ.isLoading && <Skeleton className="h-24 w-48 rounded-xl" />}
        {modelQ.isError && (
          <ErrorCard title="Could not load coverage" onRetry={() => modelQ.refetch()} className="max-w-xs" />
        )}
        {modelQ.data && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <StatCard
              title="Fund Records in Master"
              value={modelQ.data.coverage.total_funds.toLocaleString('en-IN')}
              status="neutral"
              sub="One per plan variant (Direct/Regular etc.)"
            />
            <StatCard
              title="Distinct Schemes"
              value={modelQ.data.coverage.total_schemes.toLocaleString('en-IN')}
              status="neutral"
              sub="Plan variants collapsed — matches the AMC Coverage page"
            />
            <StatCard
              title="Funds With a Current Label"
              value={modelQ.data.coverage.labelled_funds.toLocaleString('en-IN')}
              status={modelQ.data.coverage.labelled_funds > 0 ? 'healthy' : 'warning'}
              sub="Labelled in the latest nightly scoring run"
            />
          </div>
        )}
      </section>

      {/* Section D — Registry versions */}
      <Section
        id="section-registry"
        title="Version History"
        subtitle="Every scoring-model version ever registered, newest first. Created by = who registered the version's configuration; Approved by = the second person who signed off before activation. Use [Activate] on a row to make a version live. Click a column heading to sort."
      >
        {modelQ.isLoading && <TableSkeleton rows={4} />}
        {modelQ.isError && (
          <ErrorCard title="Could not load registry" onRetry={() => modelQ.refetch()} />
        )}
        {modelQ.data && <RegistryTable versions={modelQ.data.registry_versions} />}
      </Section>
    </div>
  );
}
