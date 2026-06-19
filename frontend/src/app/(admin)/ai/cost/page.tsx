'use client';

/**
 * AI Cost & Usage — /admin/ai/cost
 * Phase 4, Tier-B read-only (Admin.md §15, §18 step 4).
 *
 * Backend: AiCostResponse (aiops_schemas.py)
 * budget is NESTED under d.budget (BudgetSnapshot).
 * per_model and latency are InstrumentedFalse.
 *
 * Sections:
 *   A — Budget KPI cards (free calls used/cap/remaining · premium USD used/soft/hard/remaining)
 *       with progress bars
 *   B — "Per-model & latency breakdown — not yet instrumented" note
 *
 * Four-state contract. No advisory verbs. Numerics allowed (admin-only, §16).
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { HealthBadge } from '@/components/admin/HealthBadge';
import { StatCard } from '@/components/admin/StatCard';
import { useAdminAICost } from '@/features/admin/api';

// ---------------------------------------------------------------------------
// Static grid class maps — no dynamic interpolation
// ---------------------------------------------------------------------------
const GRID_COLS_2 = 'grid-cols-2';
const GRID_COLS_4 = 'grid-cols-4';

// ---------------------------------------------------------------------------
// Skeletons
// ---------------------------------------------------------------------------
function KpiSkeleton() {
  return (
    <div className={`grid grid-cols-2 gap-3 sm:${GRID_COLS_4}`}>
      {[...Array(4)].map((_, i) => (
        <Skeleton key={i} className="h-24 rounded-xl" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Budget progress bar
// ---------------------------------------------------------------------------
function BudgetBar({
  label,
  used,
  cap,
  unit = '',
  softCap,
  isFloat = false,
}: {
  label: string;
  used: number;
  cap: number;
  unit?: string;
  softCap?: number;
  isFloat?: boolean;
}) {
  const pct = cap > 0 ? Math.min(100, Math.round((used / cap) * 100)) : 0;
  const isCritical = cap > 0 && used >= cap;
  const isWarning = softCap != null && cap > 0 && used >= softCap && !isCritical;
  const fmt = (n: number) => (isFloat ? n.toFixed(4) : n.toLocaleString('en-IN'));

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-3">
        <span className="text-small text-ink-secondary">{label}</span>
        <span className="font-mono text-small tabular-nums text-ink font-medium">
          {unit}{fmt(used)} / {unit}{isFloat ? cap.toFixed(2) : cap.toLocaleString('en-IN')}
        </span>
      </div>
      <ProgressBar
        value={pct}
        className={
          isCritical
            ? '[&>div]:bg-red'
            : isWarning
            ? '[&>div]:bg-amber'
            : undefined
        }
      />
      {softCap != null && (
        <p className="text-caption text-ink-muted">Soft cap: {unit}{softCap}</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function AdminAICostPage() {
  const q = useAdminAICost();

  return (
    <>
      <div className="flex flex-col gap-8">
        {/* Page header */}
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-h2 font-medium text-ink">Cost & Usage</h1>
            <p className="mt-1 text-small text-ink-muted">
              AI budget-governor spend, free-tier call usage, and cap status.
              Governed OpenRouter gateway only (Admin.md §15).
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => q.refetch()}>
            <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
            Refresh
          </Button>
        </div>

        {q.isLoading && (
          <div className="flex flex-col gap-6">
            <KpiSkeleton />
            <Skeleton className="h-32 rounded-lg" />
          </div>
        )}

        {q.isError && (
          <ErrorCard
            title="Could not load cost data"
            onRetry={() => q.refetch()}
            className="max-w-md"
          />
        )}

        {q.data && (() => {
          // budget is nested under d.budget
          const b = q.data.budget;
          const allZero = b.free_calls_today === 0 && b.premium_usd_today === 0;

          return (
            <div className="flex flex-col gap-6">
              {/* Section A — Budget KPI cards */}
              <section aria-labelledby="section-budget-kpi">
                <h2 id="section-budget-kpi" className="mb-3 text-h3 font-medium text-ink">
                  Budget KPIs
                </h2>
                {allZero ? (
                  <EmptyState
                    title="No AI spend today"
                    description="Budget usage will appear here once the AI gateway processes requests."
                    className="py-8"
                  />
                ) : (
                  <div className={`grid grid-cols-2 gap-3 sm:${GRID_COLS_4}`}>
                    <StatCard
                      title="Free Calls Used"
                      value={b.free_calls_today.toLocaleString('en-IN')}
                      sub={`cap: ${b.free_cap.toLocaleString('en-IN')}`}
                      status={
                        b.free_remaining === 0
                          ? 'critical'
                          : b.free_remaining < b.free_cap * 0.1
                          ? 'warning'
                          : 'neutral'
                      }
                    />
                    <StatCard
                      title="Free Calls Remaining"
                      value={b.free_remaining.toLocaleString('en-IN')}
                      status={
                        b.free_remaining === 0
                          ? 'critical'
                          : b.free_remaining < b.free_cap * 0.1
                          ? 'warning'
                          : 'healthy'
                      }
                    />
                    <StatCard
                      title="Premium Spend"
                      value={`$${b.premium_usd_today.toFixed(4)}`}
                      sub={`soft $${b.premium_soft_cap} · hard $${b.premium_hard_cap}`}
                      status={
                        b.premium_usd_today >= b.premium_hard_cap
                          ? 'critical'
                          : b.premium_usd_today >= b.premium_soft_cap
                          ? 'warning'
                          : 'neutral'
                      }
                    />
                    <StatCard
                      title="Premium Remaining"
                      value={`$${b.premium_remaining_usd.toFixed(4)}`}
                      status={
                        b.premium_remaining_usd <= 0
                          ? 'critical'
                          : b.premium_remaining_usd < b.premium_hard_cap * 0.1
                          ? 'warning'
                          : 'healthy'
                      }
                    />
                  </div>
                )}
              </section>

              {/* Progress bars */}
              {!allZero && (
                <section aria-labelledby="section-budget-bars">
                  <Card>
                    <CardHeader>
                      <CardTitle id="section-budget-bars">Budget Progress</CardTitle>
                    </CardHeader>
                    <CardBody>
                      <div className="flex flex-col gap-5">
                        <BudgetBar
                          label="Free calls today"
                          used={b.free_calls_today}
                          cap={b.free_cap}
                        />
                        <BudgetBar
                          label="Premium spend today (USD)"
                          used={b.premium_usd_today}
                          cap={b.premium_hard_cap}
                          unit="$"
                          softCap={b.premium_soft_cap}
                          isFloat
                        />
                      </div>
                    </CardBody>
                  </Card>
                </section>
              )}

              {/* Section B — Not-yet-instrumented */}
              <section aria-labelledby="section-cost-gaps">
                <h2 id="section-cost-gaps" className="mb-3 text-h3 font-medium text-ink">
                  Planned Instrumentation
                </h2>
                <div className={`grid grid-cols-1 gap-3 sm:${GRID_COLS_2}`}>
                  <div className="rounded-lg border border-line bg-surface p-4 text-small text-ink-muted">
                    <div className="flex items-center gap-2 mb-2">
                      <p className="font-medium text-ink">Per-model breakdown</p>
                      <HealthBadge status={q.data.per_model.instrumented ? 'Healthy' : 'Planned'} />
                    </div>
                    <p>{q.data.per_model.note ?? 'Per-model cost attribution is not yet instrumented.'}</p>
                  </div>
                  <div className="rounded-lg border border-line bg-surface p-4 text-small text-ink-muted">
                    <div className="flex items-center gap-2 mb-2">
                      <p className="font-medium text-ink">Latency breakdown</p>
                      <HealthBadge status={q.data.latency.instrumented ? 'Healthy' : 'Planned'} />
                    </div>
                    <p>{q.data.latency.note ?? 'Per-call latency histograms are not yet instrumented.'}</p>
                  </div>
                </div>
              </section>
            </div>
          );
        })()}
      </div>
    </>
  );
}
