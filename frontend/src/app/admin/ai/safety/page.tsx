'use client';

/**
 * AI Safety Monitor — /admin/ai/safety
 * Phase 4, Tier-B read-only — PRIMARY COMPLIANCE SURFACE (Admin.md §15, §16, §18 step 4).
 *
 * Backend: AiSafetyResponse (aiops_schemas.py)
 *
 * Sections:
 *   A — Advice-boundary breaches card (always 0 + instrumented:false warning — NOT a clean pass)
 *   B — Served by type dict (rendered as key/value table)
 *   C — By confidence band dict (rendered as key/value table)
 *   D — Recent audit rows table (id · served_at · type · label · band · model · surface)
 *   E — Low-confidence log table (id · logged_at · surface · band · reason)
 *   F — Label churn badges (educational + mood)
 *
 * CRITICAL: instrumented:false means "not yet measured", NOT "zero violations".
 * The 0 breach count reflects rejected-at-gateway calls that are NOT recorded.
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
import { formatDateTime } from '@/components/admin/utils';
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
// Dict table — renders a Record<string, number> as a two-column table
// ---------------------------------------------------------------------------
function DictTable({ data, col1, col2 }: { data: Record<string, number>; col1: string; col2: string }) {
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
              <th key={h} className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {entries.map(([key, count]) => (
            <tr key={key} className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors">
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink">{key}</td>
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
const AUDIT_HEADERS = ['Served at', 'Type', 'Label', 'Band', 'Model', 'Surface'];

function AuditTable({ rows }: { rows: AdminAIAuditRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState title="No recent outputs" description="Recent served AI outputs will appear here." className="py-6" />
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <thead>
          <tr className="border-b border-line">
            {AUDIT_HEADERS.map((h) => (
              <th key={h} className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors">
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                {formatDateTime(row.served_at)}
              </td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink">{row.recommendation_type}</td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">{row.label ?? '—'}</td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">{row.confidence_band ?? '—'}</td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted truncate max-w-[100px]">
                {row.model ?? '—'}
              </td>
              <td className="py-2.5 font-mono text-[11px] text-ink-muted">{row.surface ?? '—'}</td>
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
const LOW_CONF_HEADERS = ['Logged at', 'Surface', 'Band', 'Score', 'Reason'];

function LowConfTable({ rows }: { rows: AdminAILowConfRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState title="No low-confidence entries" description="Low-confidence output refusals will appear here." className="py-6" />
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <thead>
          <tr className="border-b border-line">
            {LOW_CONF_HEADERS.map((h) => (
              <th key={h} className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors">
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted whitespace-nowrap">
                {formatDateTime(row.logged_at)}
              </td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink">{row.surface ?? '—'}</td>
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">{row.confidence_band ?? '—'}</td>
              <td className="py-2.5 pr-4 font-mono text-[11px] tabular-nums text-ink-muted">
                {row.confidence_score != null ? row.confidence_score.toFixed(3) : '—'}
              </td>
              <td className="py-2.5 font-mono text-[11px] text-ink-muted">{row.reason ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Label churn card
// ---------------------------------------------------------------------------
function ChurnCard({ label, churn }: { label: string; churn: AdminAILabelChurn }) {
  return (
    <div className="flex flex-col gap-1.5 rounded-lg border border-line bg-surface p-4 min-w-[220px]">
      <span className="text-caption uppercase tracking-wide text-ink-muted">{label}</span>
      <span className="font-mono text-small font-medium text-ink">{churn.decision}</span>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-caption text-ink-muted">
          churn: {(churn.churn * 100).toFixed(1)}%
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
              Primary compliance-ops surface — operationalises the SEBI advisory boundary.
              Sourced from{' '}
              <code className="font-mono text-caption">compliance.ai_recommendation_audit</code>{' '}
              and{' '}
              <code className="font-mono text-caption">compliance.ai_low_confidence_log</code>.
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

              {/* Section B — Served by type */}
              <section aria-labelledby="section-served-type">
                <Card>
                  <CardHeader>
                    <CardTitle id="section-served-type">
                      Served by Recommendation Type ({d.days}d)
                    </CardTitle>
                  </CardHeader>
                  <CardBody>
                    <DictTable data={d.served_by_type} col1="Type" col2="Count" />
                  </CardBody>
                </Card>
              </section>

              {/* Section C — By confidence band */}
              <section aria-labelledby="section-served-band">
                <Card>
                  <CardHeader>
                    <CardTitle id="section-served-band">
                      Served by Confidence Band ({d.days}d)
                    </CardTitle>
                    <p className="mt-1 text-small text-ink-muted">
                      Low-confidence total: {d.low_confidence_count.toLocaleString('en-IN')} outputs returned as{' '}
                      <code className="font-mono text-caption">insufficient_data</code>
                    </p>
                  </CardHeader>
                  <CardBody>
                    <DictTable data={d.by_confidence_band} col1="Band" col2="Count" />
                  </CardBody>
                </Card>
              </section>

              {/* Section D — Recent audit rows */}
              <section aria-labelledby="section-recent">
                <Card>
                  <CardHeader>
                    <CardTitle id="section-recent">Recent Served Outputs</CardTitle>
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
                      Outputs where confidence &lt; 0.30, returned as{' '}
                      <code className="font-mono text-caption">insufficient_data</code>.
                    </p>
                  </CardHeader>
                  <CardBody>
                    <LowConfTable rows={d.recent_low_confidence} />
                  </CardBody>
                </Card>
              </section>

              {/* Section F — Label churn */}
              <section aria-labelledby="section-churn">
                <h2 id="section-churn" className="mb-3 text-h3 font-medium text-ink">
                  Label Churn
                </h2>
                <div className="flex flex-wrap gap-4">
                  <ChurnCard label="Educational label churn" churn={d.label_churn_educational} />
                  <ChurnCard label="Mood / regime churn" churn={d.label_churn_mood} />
                </div>
              </section>

              {/* Groundedness note */}
              <section aria-labelledby="section-groundedness">
                <div className="rounded-lg border border-line bg-surface p-4 text-small text-ink-muted">
                  <div className="flex items-center gap-2 mb-2">
                    <p className="font-medium text-ink">Groundedness</p>
                    <HealthBadge status={d.groundedness.instrumented ? 'Healthy' : 'Planned'} />
                  </div>
                  <p>{d.groundedness.note ?? 'Not yet instrumented.'}</p>
                </div>
              </section>
            </div>
          );
        })()}
      </div>
    </>
  );
}
