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
 *        Per row: non-activated rows show "Gated (B6)" chip — activation disabled until B6 is resolved.
 *
 * Phase 5: Activate Version mutation (POST /admin/scoring/{version}/activate) is NOT wired from the UI.
 *   The two-person methodology gate (B6) is currently vacuous — re-enable the activation flow only after
 *   B6 is resolved and a distinct second approver identity is enforced end-to-end.
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
import { formatDateTime } from '@/components/admin/utils';
import {
  useAdminScoringModel,
  type AdminScoringRegistryVersion,
} from '@/features/admin/api';

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
            <span className="w-40 shrink-0 text-small text-ink-muted truncate">{key}</span>
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
// Registry versions table (Activate disabled pending B6)
// ---------------------------------------------------------------------------
function RegistryTable({ versions }: { versions: AdminScoringRegistryVersion[] }) {
  if (versions.length === 0) {
    return (
      <EmptyState
        title="No registry versions"
        description="Score model registry entries will appear here."
        className="py-8"
      />
    );
  }

  const HEADERS = ['Version', 'Created by', 'Approved by', '2-person OK', 'Active', 'Activated at', 'Created at', 'Activate'];

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <thead>
          <tr className="border-b border-line">
            {HEADERS.map((h) => (
              <th
                key={h}
                className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {versions.map((v) => (
            <tr
              key={v.model_version}
              className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors"
            >
              <td className="py-2.5 pr-4 font-mono text-[11px] font-medium text-ink whitespace-nowrap">
                {v.model_version}
              </td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                {v.created_by.length > 8 ? v.created_by.slice(0, 8) + '…' : v.created_by}
              </td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                {v.approved_by
                  ? (v.approved_by.length > 8 ? v.approved_by.slice(0, 8) + '…' : v.approved_by)
                  : '—'}
              </td>
              <td className="py-2.5 pr-4">
                <HealthBadge status={v.two_person_ok ? 'Success' : 'Warning'} />
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
                  <span
                    title="Activation is disabled pending the two-person methodology gate (B6). A second distinct approver identity must be wired before any scoring version can be activated from the console."
                    className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-mono font-medium bg-amber/10 text-amber border border-amber/30 cursor-not-allowed select-none"
                  >
                    Gated (B6)
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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
            Activation via console is disabled pending B6 (two-person methodology gate).
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => modelQ.refetch()}>
          <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
          Refresh
        </Button>
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
                    <HealthBadge status="Warning" />
                  )}
                  {modelQ.data.provisional && (
                    <span className="text-small text-amber">Provisional</span>
                  )}
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="text-caption uppercase tracking-wide text-ink-muted">Created by</span>
                <span className="font-mono text-small text-ink">
                  {modelQ.data.created_by.length > 12
                    ? modelQ.data.created_by.slice(0, 12) + '…'
                    : modelQ.data.created_by}
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
        subtitle="Internal model weights — numerics visible here (admin-only, Admin.md §16). Not exposed on the public product surface."
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
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard
              title="Funds Scored"
              value={modelQ.data.coverage.total_funds.toLocaleString('en-IN')}
              status="neutral"
            />
          </div>
        )}
      </section>

      {/* Section D — Registry versions (Activate disabled pending B6) */}
      <Section
        id="section-registry"
        title="Registry Versions"
        subtitle="All model versions in the ranking_configs registry. Activation via console is disabled pending B6 (two-person methodology gate)."
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
