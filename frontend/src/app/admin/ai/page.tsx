'use client';

/**
 * AI Ops Dashboard — /admin/ai
 * Phase 4, Tier-B read-only (Admin.md §15, §16, §18 step 4).
 *
 * KPI row: model version · activated status · budget free calls (used/cap) ·
 *          budget premium ($used/$cap) · served 7d · low-confidence 7d ·
 *          label-churn decision.
 *
 * Four-state contract: skeleton / empty / error+retry / data.
 * No advisory verbs. Numeric values allowed (admin-only, §16).
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { RefreshCw, Bot } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { StatCard } from '@/components/admin/StatCard';
import { HealthBadge } from '@/components/admin/HealthBadge';
import { useAdminAIDashboard } from '@/features/admin/api';
import { displayLabel } from '@/lib/displayLabel';
import { formatRelative } from '@/components/admin/utils';

// ---------------------------------------------------------------------------
// Skeleton row — 6 StatCards
// ---------------------------------------------------------------------------
const GRID_COLS_3 = 'grid-cols-3';

function KpiSkeleton() {
  return (
    <div className={`grid grid-cols-2 gap-3 sm:${GRID_COLS_3}`}>
      {[...Array(6)].map((_, i) => (
        <Skeleton key={i} className="h-24 rounded-xl" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dashboard page
// ---------------------------------------------------------------------------
export default function AdminAIDashboardPage() {
  const q = useAdminAIDashboard();

  return (
    <>
      <div className="flex flex-col gap-8">
        {/* Page header */}
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-h2 font-medium text-ink">AI Ops Dashboard</h1>
            <p className="mt-1 text-small text-ink-muted">
              Live model status, budget usage, and output quality at a glance.
              Reads from the AI output log.
            </p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <Button variant="ghost" size="sm" onClick={() => q.refetch()}>
              <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
              Refresh
            </Button>
            {q.dataUpdatedAt ? (
              <span className="text-[10px] text-ink-muted">
                Last updated {formatRelative(new Date(q.dataUpdatedAt).toISOString())}
              </span>
            ) : null}
          </div>
        </div>

        {/* KPI row */}
        <section aria-labelledby="section-ai-kpi">
          <h2 id="section-ai-kpi" className="mb-3 text-h3 font-medium text-ink">
            Key Indicators
          </h2>

          {q.isLoading && <KpiSkeleton />}

          {q.isError && (
            <ErrorCard
              title="Could not load AI dashboard"
              onRetry={() => q.refetch()}
              className="max-w-md"
            />
          )}

          {q.data && (() => {
            const d = q.data;
            const allZero =
              d.served_7d === 0 &&
              d.low_confidence_7d === 0 &&
              d.budget.free_calls_today === 0 &&
              d.budget.premium_usd_today === 0;

            if (allZero && !d.activated && d.label_churn.decision === 'insufficient_data') {
              return (
                <EmptyState
                  icon={<Bot size={32} />}
                  title="No AI activity yet"
                  description="AI ops metrics will appear once the model is activated and serving outputs."
                  className="py-12"
                />
              );
            }

            return (
              <div className={`grid grid-cols-2 gap-3 sm:${GRID_COLS_3}`}>
                {/* Model live / version */}
                <StatCard
                  title="Model Version"
                  value={`Model: ${d.model_version}`}
                  sub={d.activated ? 'activated' : 'not activated'}
                  status={d.activated ? 'healthy' : 'warning'}
                />
                {/* Budget — free calls */}
                <StatCard
                  title="Free Calls Today"
                  value={
                    (d.budget as { available?: boolean }).available === false
                      ? '—'
                      : `${d.budget.free_calls_today} / ${d.budget.free_cap}`
                  }
                  sub={
                    (d.budget as { available?: boolean }).available === false
                      ? 'Live usage data unavailable'
                      : `${d.budget.free_remaining} remaining · Free-tier AI model calls used today`
                  }
                  status={
                    (d.budget as { available?: boolean }).available === false
                      ? 'neutral'
                      : d.budget.free_remaining === 0
                      ? 'critical'
                      : d.budget.free_remaining < d.budget.free_cap * 0.1
                      ? 'warning'
                      : 'neutral'
                  }
                />
                {/* Budget — premium USD */}
                <StatCard
                  title="Premium Spend Today"
                  value={
                    (d.budget as { available?: boolean }).available === false
                      ? '—'
                      : `$${d.budget.premium_usd_today.toFixed(4)}`
                  }
                  sub={
                    (d.budget as { available?: boolean }).available === false
                      ? 'Live usage data unavailable'
                      : `Warning at $${d.budget.premium_soft_cap} · Stops at $${d.budget.premium_hard_cap} · Paid AI spend today (USD)`
                  }
                  status={
                    (d.budget as { available?: boolean }).available === false
                      ? 'neutral'
                      : d.budget.premium_usd_today >= d.budget.premium_hard_cap
                      ? 'critical'
                      : d.budget.premium_usd_today >= d.budget.premium_soft_cap
                      ? 'warning'
                      : 'neutral'
                  }
                />
                {/* Served 7d */}
                <StatCard
                  title="Outputs Served (7d)"
                  value={d.served_7d.toLocaleString('en-IN')}
                  status="neutral"
                />
                {/* Low confidence 7d */}
                <StatCard
                  title="Low-Confidence (7d)"
                  value={d.low_confidence_7d.toLocaleString('en-IN')}
                  sub="Times the AI declined to answer because it wasn't sure enough · Counter not yet wired — currently always 0"
                  status={d.low_confidence_7d > 0 ? 'warning' : 'neutral'}
                />
                {/* Label churn */}
                <StatCard
                  title="Label Churn"
                  value={displayLabel(d.label_churn.decision, 'decision')}
                  sub={`How often the same fund's label changed — high churn means review needed · ${(d.label_churn.churn * 100).toFixed(1)}%${d.label_churn.requires_human_review ? ' · review needed' : ''}`}
                  status={
                    d.label_churn.requires_human_review
                      ? 'warning'
                      : d.label_churn.churn > 0.1
                      ? 'warning'
                      : 'healthy'
                  }
                />
              </div>
            );
          })()}
        </section>

        {/* Live status badge */}
        {q.data && (
          <section aria-labelledby="section-ai-status" className="flex items-center gap-3">
            <span className="text-small text-ink-muted">Model status:</span>
            <HealthBadge status={q.data.activated ? 'Healthy' : 'Paused'} />
            <span className="font-mono text-[11px] text-ink-muted">Model: {q.data.model_version}</span>
          </section>
        )}
      </div>
    </>
  );
}
