'use client';

/**
 * AI Safety Monitor — /admin/ai/safety
 * Phase 4, Tier-B read-only — PRIMARY COMPLIANCE SURFACE (Admin.md §15, §16, §18 step 4).
 *
 * Backend: AiSafetyResponse (aiops_schemas.py)
 *
 * Sections:
 *   A — Advice-boundary breaches card (always 0 + instrumented:false warning — NOT a clean pass)
 *   B — AI Outputs by Category dict (rendered as key/value table)
 *   C — AI Outputs by Certainty Level dict (rendered as key/value table)
 *   D — Recent audit rows table (id · served_at · category · label · certainty · model · where shown)
 *   E — Low-confidence log table (id · logged_at · where shown · certainty · score · reason)
 *   F — Label Stability badges (fund evaluation + market mood)
 *
 * CRITICAL: instrumented:false means "not yet measured", NOT "zero violations".
 * The 0 breach count reflects blocked AI responses that are NOT yet recorded.
 *
 * Four-state contract. No advisory verbs.
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { RefreshCw, ShieldAlert, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { HealthBadge } from '@/components/admin/HealthBadge';
import { formatDateTime, formatRelative } from '@/components/admin/utils';
import { displayLabel, modelLabel, titleCase } from '@/lib/displayLabel';
import { SortableTh, useSort, type SortAccessor } from '@/components/admin/sortable';
import {
  useAdminAISafety,
  type AdminAILabelChurn,
  type AdminAIAuditRow,
  type AdminAILowConfRow,
} from '@/features/admin/api';

// ---------------------------------------------------------------------------
// Skeletons
// ---------------------------------------------------------------------------
function CardSkeleton() {
  return <Skeleton className="h-32 rounded-lg" />;
}

function TableSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {[...Array(5)].map((_, i) => (
        <Skeleton key={i} className="h-10 rounded-md" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dict table — renders a Record<string, number> as a two-column table,
// applying displayLabel to the key column.
// ---------------------------------------------------------------------------
function DictTable({
  data,
  col1,
  col2,
  labelDomain,
}: {
  data: Record<string, number>;
  col1: string;
  col2: string;
  labelDomain?: Parameters<typeof displayLabel>[1];
}) {
  const entries = Object.entries(data);
  if (entries.length === 0) {
    return (
      <EmptyState title="No data yet" description="Counts will appear once the AI gateway logs outputs." className="py-6" />
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <thead>
          <tr className="border-b border-line">
            {[col1, col2].map((h) => (
              <th key={h} scope="col" className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {entries.map(([key, count]) => (
            <tr key={key} className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors">
              <td className="py-2.5 pr-4 text-[11px] text-ink">
                {labelDomain ? displayLabel(key, labelDomain) : displayLabel(key)}
              </td>
              <td className="py-2.5 font-mono text-[11px] tabular-nums text-right text-ink font-medium">
                {count.toLocaleString('en-IN')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Recent audit rows table
// ---------------------------------------------------------------------------
const AUDIT_ACCESSORS: Record<string, SortAccessor<AdminAIAuditRow>> = {
  served_at: (r) => r.served_at,
  category: (r) => displayLabel(r.recommendation_type, 'recoType'),
  label: (r) => (r.label ? displayLabel(r.label, 'label') : null),
  band: (r) => r.confidence_band,
  model: (r) => (r.model ? modelLabel(r.model) : null),
  surface: (r) => (r.surface ? displayLabel(r.surface, 'surface') : null),
};

function AuditTable({ rows }: { rows: AdminAIAuditRow[] }) {
  const { sorted, sort, toggle } = useSort(rows, AUDIT_ACCESSORS, { key: 'served_at', dir: 'desc' });
  if (rows.length === 0) {
    return (
      <EmptyState title="No recent outputs" description="Recent served AI outputs will appear here." className="py-6" />
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small" aria-label="Recent AI outputs">
        <caption className="sr-only">
          Recent AI outputs served to users, sourced from the AI output log.
        </caption>
        <thead>
          <tr className="border-b border-line">
            <SortableTh label="Served at" sortKey="served_at" sort={sort} onToggle={toggle} />
            <SortableTh label="Category" sortKey="category" sort={sort} onToggle={toggle} />
            <SortableTh label="Label" sortKey="label" sort={sort} onToggle={toggle} />
            <SortableTh label="Certainty" sortKey="band" sort={sort} onToggle={toggle} />
            <SortableTh label="AI Model" sortKey="model" sort={sort} onToggle={toggle} />
            <SortableTh label="Where Shown" sortKey="surface" sort={sort} onToggle={toggle} />
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.id} className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors">
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                {formatDateTime(row.served_at)}
              </td>
              <td className="py-2.5 pr-4 text-[11px] text-ink">
                {displayLabel(row.recommendation_type, 'recoType')}
              </td>
              <td className="py-2.5 pr-4 text-[11px] text-ink-muted">
                {row.label ? displayLabel(row.label, 'label') : '—'}
              </td>
              <td className="py-2.5 pr-4 text-[11px] text-ink-muted">
                {row.confidence_band ? displayLabel(row.confidence_band, 'band') : '—'}
              </td>
              <td className="py-2.5 pr-4 text-[11px] text-ink-muted truncate max-w-[120px]" title={row.model ?? undefined}>
                {row.model ? modelLabel(row.model) : '—'}
              </td>
              <td className="py-2.5 text-[11px] text-ink-muted" title={row.surface ?? undefined}>
                {row.surface ? displayLabel(row.surface, 'surface') : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Low-confidence log table
// ---------------------------------------------------------------------------
const LOW_CONF_ACCESSORS: Record<string, SortAccessor<AdminAILowConfRow>> = {
  logged_at: (r) => r.logged_at,
  surface: (r) => (r.surface ? displayLabel(r.surface, 'surface') : null),
  band: (r) => r.confidence_band,
  score: (r) => r.confidence_score,
  reason: (r) => r.reason,
};

function LowConfTable({ rows }: { rows: AdminAILowConfRow[] }) {
  const { sorted, sort, toggle } = useSort(rows, LOW_CONF_ACCESSORS, { key: 'logged_at', dir: 'desc' });
  if (rows.length === 0) {
    return (
      <EmptyState title="No refusals recorded" description="Every time the AI declines to answer because it is not certain enough, the refusal is logged here." className="py-6" />
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <thead>
          <tr className="border-b border-line">
            <SortableTh label="Logged at" sortKey="logged_at" sort={sort} onToggle={toggle} />
            <SortableTh label="Where Shown" sortKey="surface" sort={sort} onToggle={toggle} />
            <SortableTh label="Certainty" sortKey="band" sort={sort} onToggle={toggle} />
            <SortableTh label="Certainty Score" sortKey="score" sort={sort} onToggle={toggle} />
            <SortableTh label="Reason" sortKey="reason" sort={sort} onToggle={toggle} />
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.id} className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors">
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                {formatDateTime(row.logged_at)}
              </td>
              <td className="py-2.5 pr-4 text-[11px] text-ink" title={row.surface ?? undefined}>
                {row.surface ? displayLabel(row.surface, 'surface') : '—'}
              </td>
              <td className="py-2.5 pr-4 text-[11px] text-ink-muted">
                {row.confidence_band ? displayLabel(row.confidence_band, 'band') : '—'}
              </td>
              <td
                className="py-2.5 pr-4 font-mono text-[11px] tabular-nums text-ink-muted"
                title={row.confidence_score != null ? `Raw score: ${row.confidence_score.toFixed(3)} (0 = no certainty, 1 = full certainty)` : undefined}
              >
                {row.confidence_score != null ? `${Math.round(row.confidence_score * 100)}%` : '—'}
              </td>
              <td className="py-2.5 text-[11px] text-ink-muted" title={row.reason ?? undefined}>
                {row.reason ? titleCase(row.reason) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Label stability card (formerly "churn card")
// ---------------------------------------------------------------------------
function StabilityCard({ label, churn }: { label: string; churn: AdminAILabelChurn }) {
  const churnPct = (churn.churn * 100).toFixed(1);
  return (
    <div className="flex flex-col gap-1.5 rounded-lg border border-line bg-surface p-4 min-w-[220px]">
      <span className="text-caption uppercase tracking-wide text-ink-muted">{label}</span>
      <span className="text-[11px] text-ink">{displayLabel(churn.decision, 'decision')}</span>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-caption text-ink-muted">
          Changed: {churnPct}% of signals
        </span>
        {churn.requires_human_review && (
          <HealthBadge status="Warning" />
        )}
      </div>
      {churn.reason && (
        <span className="text-caption text-ink-muted">{churn.reason}</span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function AdminAISafetyPage() {
  const q = useAdminAISafety();

  return (
    <>
      <div className="flex flex-col gap-8">
        {/* Page header */}
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-h2 font-medium text-ink">Safety Monitor</h1>
            <p className="mt-1 text-small text-ink-muted">
              The main compliance page — it checks that every AI output stays educational and never gives investment advice (the SEBI boundary).
              Sourced from the AI output log and the low-confidence refusal log.
              {q.dataUpdatedAt ? (
                <> Last updated {formatRelative(new Date(q.dataUpdatedAt).toISOString())}.</>
              ) : null}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => q.refetch()}>
            <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
            Refresh
          </Button>
        </div>

        {q.isLoading && (
          <div className="flex flex-col gap-6">
            <CardSkeleton />
            <TableSkeleton />
          </div>
        )}

        {q.isError && (
          <ErrorCard
            title="Could not load safety data"
            onRetry={() => q.refetch()}
            className="max-w-md"
          />
        )}

        {!q.isLoading && !q.isError && !q.data && (
          <EmptyState
            icon={<ShieldAlert size={32} />}
            title="No safety data available"
            description="Safety monitor data will appear once the AI gateway is active and logging outputs."
            className="py-16"
          />
        )}

        {q.data && (() => {
          const d = q.data;
          return (
            <div className="flex flex-col gap-6">
              {/* Section A — Advice-boundary breaches */}
              <section aria-labelledby="section-breaches">
                <Card>
                  <CardHeader>
                    <CardTitle id="section-breaches">Advice-Boundary Breaches</CardTitle>
                    <p className="mt-1 text-small text-ink-muted">
                      Counts AI responses the advisory screen rejected for crossing the educational,
                      non-advisory boundary. Rejected responses are filtered before they reach users —
                      a breach means the model tried and the gate held, never that advice was shown.
                    </p>
                  </CardHeader>
                  <CardBody>
                    <div className="flex items-start gap-4">
                      <div className="flex flex-col gap-1.5 min-w-[120px]">
                        <span className="text-caption uppercase tracking-wide text-ink-muted">Recorded value</span>
                        <span className="font-mono text-h2 font-medium tabular-nums text-ink">
                          {d.advice_boundary_breaches.value}
                        </span>
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <span className="text-caption uppercase tracking-wide text-ink-muted">Measurement status</span>
                        <HealthBadge status={d.advice_boundary_breaches.instrumented ? 'Healthy' : 'Planned'} />
                      </div>
                    </div>
                    {d.advice_boundary_breaches.instrumented && (
                      <p className="mt-3 text-small text-ink-muted">
                        Rejections recorded over the last {d.advice_boundary_breaches.window_days} days
                        {d.advice_boundary_breaches.value === 0
                          ? ' — 0 means the boundary held with no breaches.'
                          : '. Each is a blocked response, not advice shown to a user.'}
                      </p>
                    )}
                    {!d.advice_boundary_breaches.instrumented && (
                      <div className="mt-4 flex items-start gap-2 rounded-lg border border-amber/30 bg-amber/5 p-4">
                        <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber" aria-hidden="true" />
                        <div className="text-small text-ink-muted">
                          <p className="font-medium text-ink mb-1">Not yet measured — this 0 is not a clean pass</p>
                          <p>{d.advice_boundary_breaches.note}</p>
                        </div>
                      </div>
                    )}
                  </CardBody>
                </Card>
              </section>

              {/* Section B — AI Outputs by Category */}
              <section aria-labelledby="section-served-type">
                <Card>
                  <CardHeader>
                    <CardTitle id="section-served-type">
                      AI Outputs by Category ({d.days}d)
                    </CardTitle>
                    <p className="mt-1 text-small text-ink-muted">
                      Count of AI-generated outputs delivered to users, grouped by output category.
                    </p>
                  </CardHeader>
                  <CardBody>
                    <DictTable data={d.served_by_type} col1="Category" col2="Count" labelDomain="recoType" />
                  </CardBody>
                </Card>
              </section>

              {/* Section C — AI Outputs by Certainty Level */}
              <section aria-labelledby="section-served-band">
                <Card>
                  <CardHeader>
                    <CardTitle id="section-served-band">
                      AI Outputs by Certainty Level ({d.days}d)
                    </CardTitle>
                    <p className="mt-1 text-small text-ink-muted">
                      Outputs grouped by certainty level. Low-certainty total:{' '}
                      {d.low_confidence_count.toLocaleString('en-IN')} outputs returned as “Not Enough Data”
                      rather than a label.
                    </p>
                  </CardHeader>
                  <CardBody>
                    <DictTable data={d.by_confidence_band} col1="Certainty" col2="Count" labelDomain="band" />
                  </CardBody>
                </Card>
              </section>

              {/* Section D — Recent audit rows */}
              <section aria-labelledby="section-recent">
                <Card>
                  <CardHeader>
                    <CardTitle id="section-recent">Recent Served Outputs</CardTitle>
                    <p className="mt-1 text-small text-ink-muted">
                      The most recent AI outputs logged in the AI output log.
                    </p>
                  </CardHeader>
                  <CardBody>
                    <AuditTable rows={d.recent_audit_rows} />
                  </CardBody>
                </Card>
              </section>

              {/* Section E — Low-confidence log */}
              <section aria-labelledby="section-low-conf">
                <Card>
                  <CardHeader>
                    <CardTitle id="section-low-conf">Low-Confidence Log</CardTitle>
                    <p className="mt-1 text-small text-ink-muted">
                      Outputs where certainty was too low to serve a label — returned as “Not Enough Data”
                      rather than shown to users.
                    </p>
                  </CardHeader>
                  <CardBody>
                    <LowConfTable rows={d.recent_low_confidence} />
                  </CardBody>
                </Card>
              </section>

              {/* Section F — Label Stability */}
              <section aria-labelledby="section-stability">
                <h2 id="section-stability" className="mb-2 text-h3 font-medium text-ink">
                  Label Stability
                </h2>
                <p className="mb-3 text-small text-ink-muted">
                  How consistently AI outputs agree across consecutive runs. High change rates may
                  indicate unstable input data or a shift in how the model scores — not necessarily an error.
                </p>
                <div className="flex flex-wrap gap-4">
                  <StabilityCard label="Fund evaluation consistency" churn={d.label_churn_educational} />
                  <StabilityCard label="Market mood consistency" churn={d.label_churn_mood} />
                </div>
              </section>

              {/* AI Output Accuracy note */}
              <section aria-labelledby="section-groundedness">
                <div className="rounded-lg border border-line bg-surface p-4 text-small text-ink-muted">
                  <div className="flex items-center gap-2 mb-2">
                    <p className="font-medium text-ink">AI Output Accuracy Check</p>
                    <HealthBadge status={d.groundedness.instrumented ? 'Healthy' : 'Planned'} />
                  </div>
                  {d.groundedness.instrumented && d.groundedness.value !== null ? (
                    <p>
                      Average accuracy score{' '}
                      <span className="font-mono text-ink">
                        {(d.groundedness.value * 100).toFixed(0)}%
                      </span>{' '}
                      across {d.groundedness.sample_count.toLocaleString('en-IN')} sampled
                      outputs ({d.groundedness.window_days}d)
                      {d.groundedness.low_flags > 0
                        ? ` · ${d.groundedness.low_flags.toLocaleString('en-IN')} flagged low`
                        : ''}
                      .
                    </p>
                  ) : (
                    <p>{d.groundedness.note ?? 'Not yet available.'}</p>
                  )}
                </div>
              </section>
            </div>
          );
        })()}
      </div>
    </>
  );
}
