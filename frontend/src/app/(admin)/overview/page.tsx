'use client';

/**
 * Admin Overview — /admin/overview
 *
 * Single-screen health dashboard. Answers "is the platform healthy?" in <10s.
 * Layout: KPI row → Compliance glance → Recent Failures → Recent Signups → Recent Alerts
 *
 * Four-state contract per data region: Default · Loading (skeleton) · Empty · Error+Retry
 * Numeric values ARE allowed (admin-only, §16).
 * No advisory verbs (SEBI boundary still applies to copy).
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { StatCard } from '@/components/admin/StatCard';
import { HealthBadge } from '@/components/admin/HealthBadge';
import { AlertList } from '@/components/admin/AlertList';
import { useAdminHealth } from '@/features/admin/api';
import { formatRelative, formatDateTime } from '@/components/admin/utils';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// KPI skeleton row
// ---------------------------------------------------------------------------
function KPIRowSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {[...Array(5)].map((_, i) => (
        <Skeleton key={i} className="h-24 rounded-xl" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Recent Failures table
// ---------------------------------------------------------------------------
function RecentFailuresTable({
  failures,
}: {
  failures: Array<{ source: string; reason: string; failed_at: string }>;
}) {
  if (failures.length === 0) {
    return (
      <EmptyState
        title="No recent failures"
        description="All sources are reporting clean runs."
        className="py-8"
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <thead>
          <tr className="border-b border-line">
            {['Source', 'Reason', 'Time'].map((h) => (
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
          {failures.map((f, i) => (
            <tr key={i} className="border-b border-line last:border-0">
              <td className="py-2.5 pr-4 font-medium text-ink">{f.source}</td>
              <td className="py-2.5 pr-4 text-red">{f.reason}</td>
              <td className="py-2.5 font-mono text-[11px] text-ink-muted">
                {formatRelative(f.failed_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Recent Signups feed
// ---------------------------------------------------------------------------
function RecentSignupsList({
  signups,
}: {
  signups: Array<{ display_name: string; plan: string; joined_at: string }>;
}) {
  if (signups.length === 0) {
    return (
      <EmptyState
        title="No recent signups"
        description="New users will appear here."
        className="py-8"
      />
    );
  }

  return (
    <ul className="flex flex-col gap-0" role="list">
      {signups.map((s, i) => (
        <li
          key={i}
          className="flex items-center justify-between border-b border-line py-2.5 last:border-0"
        >
          <div className="flex items-center gap-3">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-royal/10 text-royal text-caption font-medium shrink-0">
              {s.display_name.charAt(0).toUpperCase()}
            </div>
            <span className="text-small font-medium text-ink">{s.display_name}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className={cn(
              'rounded-full px-2 py-0.5 text-caption font-medium',
              s.plan === 'plus' || s.plan === 'founder_lifetime'
                ? 'bg-emerald/10 text-emerald'
                : 'bg-surface-2 text-ink-muted',
            )}>
              {s.plan}
            </span>
            <span className="font-mono text-[11px] text-ink-muted">{formatRelative(s.joined_at)}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Compliance Glance pair
// ---------------------------------------------------------------------------
function ComplianceGlance({
  breaches,
  flagsCount,
}: {
  breaches: number;
  flagsCount: number;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <StatCard
        title="Advice-boundary breaches today"
        value={breaches}
        status={breaches > 0 ? 'critical' : 'healthy'}
        sub="from ai_recommendation_audit"
      />
      <StatCard
        title="Low-groundedness flags (7d)"
        value={flagsCount}
        status={flagsCount > 0 ? 'warning' : 'healthy'}
        sub="from ai_recommendation_audit"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overview page
// ---------------------------------------------------------------------------
export default function AdminOverviewPage() {
  const { data, isLoading, isError, refetch } = useAdminHealth();

  // --- Loading state ---
  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-h2 font-medium text-ink">Overview</h1>
          <p className="mt-1 text-small text-ink-muted">Platform health at a glance</p>
        </div>
        <KPIRowSkeleton />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
        </div>
        <Skeleton className="h-40 rounded-xl" />
        <Skeleton className="h-40 rounded-xl" />
      </div>
    );
  }

  // --- Error state ---
  if (isError) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-h2 font-medium text-ink">Overview</h1>
        </div>
        <ErrorCard
          title="Could not load admin health data"
          message="Check backend connectivity or try again."
          onRetry={() => refetch()}
          className="max-w-md"
        />
      </div>
    );
  }

  // --- Default (data) state ---
  const sourcesStatus =
    data!.sources_healthy < data!.sources_total ? 'warning' : 'healthy';
  const systemStatus: 'healthy' | 'warning' | 'critical' =
    data!.recent_failures.length > 3
      ? 'critical'
      : data!.recent_failures.length > 0
        ? 'warning'
        : 'healthy';

  return (
    <div className="flex flex-col gap-6">
      {/* Page header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-h2 font-medium text-ink">Overview</h1>
          <p className="mt-1 text-small text-ink-muted">Platform health at a glance</p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => refetch()}>
          <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
          Refresh
        </Button>
      </div>

      {/* KPI row — 5 cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard
          title="Sources Healthy"
          value={`${data!.sources_healthy} / ${data!.sources_total}`}
          status={sourcesStatus}
        />
        <StatCard
          title="Last NAV Sync"
          value={data!.last_nav_sync ? formatRelative(data!.last_nav_sync) : '—'}
          sub={data!.last_nav_sync ? formatDateTime(data!.last_nav_sync) : undefined}
          status={data!.last_nav_sync ? 'healthy' : 'warning'}
        />
        <StatCard
          title="Active Users"
          value={data!.active_users.toLocaleString('en-IN')}
          status="neutral"
        />
        <StatCard
          title="Premium Users"
          value={data!.premium_users.toLocaleString('en-IN')}
          status="neutral"
        />
        <StatCard
          title="System Health"
          value={
            <HealthBadge
              status={
                systemStatus === 'critical'
                  ? 'Critical'
                  : systemStatus === 'warning'
                    ? 'Warning'
                    : 'Healthy'
              }
            />
          }
          status={systemStatus}
        />
      </div>

      {/* Compliance glance */}
      <div>
        <h2 className="mb-3 text-h3 font-medium text-ink">Compliance Glance</h2>
        <ComplianceGlance
          breaches={data!.advice_boundary_breaches_today}
          flagsCount={data!.low_groundedness_flags_7d}
        />
      </div>

      {/* Recent Failures */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Failures</CardTitle>
        </CardHeader>
        <CardBody>
          <RecentFailuresTable failures={data!.recent_failures} />
        </CardBody>
      </Card>

      {/* Recent Signups */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Signups</CardTitle>
        </CardHeader>
        <CardBody>
          <RecentSignupsList signups={data!.recent_signups} />
        </CardBody>
      </Card>

      {/* Recent Alerts */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Alerts</CardTitle>
        </CardHeader>
        <CardBody>
          <AlertList alerts={data!.recent_alerts} />
        </CardBody>
      </Card>
    </div>
  );
}
