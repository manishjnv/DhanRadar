'use client';

/**
 * AI Cost & Usage — /admin/ai/cost
 * Phase 4 (read) + Phase 5 (mutations) — Tier-B.
 *
 * Read: budget KPIs, progress bars, per-model/latency notes.
 * Mutations (Phase 5 live):
 *   - Set Budget Caps: form (free_cap, premium_soft_usd, premium_hard_usd, optional reset)
 *     → confirm → POST /admin/ai/cost/caps
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
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { useAdminAICost, useAdminSetBudgetCaps } from '@/features/admin/api';

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
  const setCapsM = useAdminSetBudgetCaps();

  const [capsOpen, setCapsOpen] = React.useState(false);
  const [freeCap, setFreeCap] = React.useState('');
  const [softUsd, setSoftUsd] = React.useState('');
  const [hardUsd, setHardUsd] = React.useState('');
  const [resetCaps, setResetCaps] = React.useState(false);

  function openCapsDialog() {
    // Pre-fill with current values if available
    const b = q.data?.budget;
    setFreeCap(b ? String(b.free_cap) : '');
    setSoftUsd(b ? String(b.premium_soft_cap) : '');
    setHardUsd(b ? String(b.premium_hard_cap) : '');
    setResetCaps(false);
    setCapsOpen(true);
  }

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
          <div className="flex items-center gap-2">
            <Button size="sm" variant="secondary" onClick={openCapsDialog}>
              Set Budget Caps
            </Button>
            <Button variant="ghost" size="sm" onClick={() => q.refetch()}>
              <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
              Refresh
            </Button>
          </div>
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

      {/* Set Budget Caps dialog */}
      <ConfirmDialog
        open={capsOpen}
        onClose={() => setCapsOpen(false)}
        title="Set AI budget caps"
        description="Update the budget-governor caps for the AI gateway. Hard cap enforcement is immediate. Soft cap triggers a warning but does not block requests."
        confirmLabel="Update Caps"
        confirmVariant="primary"
        onConfirm={async () => {
          const fc = parseInt(freeCap, 10);
          const su = parseFloat(softUsd);
          const hu = parseFloat(hardUsd);
          if (!fc || fc <= 0) throw new Error('Free cap must be a positive integer.');
          if (!su || su <= 0) throw new Error('Premium soft cap must be a positive number.');
          if (!hu || hu <= 0) throw new Error('Premium hard cap must be a positive number.');
          if (su >= hu) throw new Error('Soft cap must be less than hard cap.');
          await setCapsM.mutateAsync({
            free_cap: fc,
            premium_soft_usd: su,
            premium_hard_usd: hu,
            reset: resetCaps || undefined,
          });
        }}
      >
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="caps-free" className="text-small font-medium text-ink">
              Free calls cap (daily) <span className="text-red">*</span>
            </label>
            <input
              id="caps-free"
              type="number"
              min="1"
              step="1"
              value={freeCap}
              onChange={(e) => setFreeCap(e.target.value)}
              placeholder="e.g. 500"
              className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink font-mono placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-royal/40"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="caps-soft" className="text-small font-medium text-ink">
              Premium soft cap (USD/day) <span className="text-red">*</span>
            </label>
            <input
              id="caps-soft"
              type="number"
              min="0.01"
              step="0.01"
              value={softUsd}
              onChange={(e) => setSoftUsd(e.target.value)}
              placeholder="e.g. 0.5"
              className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink font-mono placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-royal/40"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="caps-hard" className="text-small font-medium text-ink">
              Premium hard cap (USD/day) <span className="text-red">*</span>
            </label>
            <input
              id="caps-hard"
              type="number"
              min="0.01"
              step="0.01"
              value={hardUsd}
              onChange={(e) => setHardUsd(e.target.value)}
              placeholder="e.g. 2.0"
              className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink font-mono placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-royal/40"
            />
          </div>
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={resetCaps}
              onChange={(e) => setResetCaps(e.target.checked)}
              className="rounded border border-line accent-royal"
            />
            <span className="text-small text-ink-secondary">
              Reset today&apos;s counter (clear accumulated spend/calls)
            </span>
          </label>
        </div>
      </ConfirmDialog>
    </>
  );
}
