'use client';

/**
 * Admin Notifications — /admin/notifications
 * Tier-A read-only page (Admin.md §14 Notifications).
 *
 * Sections:
 *   A — Queue health KPIs (telegram depth · email depth · sent · failed · rate_capped · deferred · last_sent_at)
 *   B — Template list (template ids from the in-code list)
 *   C — Broadcast composer affordance (disabled, Phase 5; shows broadcast_available state)
 *
 * Four-state contract: skeleton / empty / error+retry / data.
 * No advisory verbs.
 * Broadcast composer is a gated mutation (Phase 5) — shown disabled only.
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
import { formatRelative } from '@/components/admin/utils';
import { useAdminNotificationsHealth } from '@/features/admin/api';

// ---------------------------------------------------------------------------
// Static class maps — Tailwind JIT cannot see interpolated class names
// ---------------------------------------------------------------------------
const GRID_COLS_4 = 'grid-cols-4';

// ---------------------------------------------------------------------------
// Skeletons
// ---------------------------------------------------------------------------
function StatRowSkeleton({ cols }: { cols: number }) {
  const lg = cols === 4 ? GRID_COLS_4 : 'grid-cols-3';
  return (
    <div className={`grid grid-cols-2 gap-3 sm:${lg}`}>
      {[...Array(cols)].map((_, i) => (
        <Skeleton key={i} className="h-24 rounded-xl" />
      ))}
    </div>
  );
}

function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2">
      {[...Array(rows)].map((_, i) => (
        <Skeleton key={i} className="h-9 rounded-md" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Notifications page
// ---------------------------------------------------------------------------
export default function AdminNotificationsPage() {
  const healthQ = useAdminNotificationsHealth();

  return (
    <div className="flex flex-col gap-8">
      {/* Page header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-h2 font-medium text-ink">Notifications</h1>
          <p className="mt-1 text-small text-ink-muted">
            Queue health · templates · broadcast composer (Phase 5).
            Sourced from the notify-drain task.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => healthQ.refetch()}>
          <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
          Refresh
        </Button>
      </div>

      {/* Section A — Queue health KPIs */}
      <section aria-labelledby="section-queue-health">
        <h2 id="section-queue-health" className="mb-3 text-h3 font-medium text-ink">
          Queue Health
        </h2>
        {healthQ.isLoading && <StatRowSkeleton cols={4} />}
        {healthQ.isError && (
          <ErrorCard
            title="Could not load notification health"
            onRetry={() => healthQ.refetch()}
            className="max-w-md"
          />
        )}
        {healthQ.data && (() => {
          const d = healthQ.data;
          const lastSentLabel = d.last_sent_at
            ? formatRelative(d.last_sent_at)
            : 'Never';
          return (
            <>
              {/* Queue depth row */}
              <div className={`grid grid-cols-2 gap-3 sm:${GRID_COLS_4} mb-3`}>
                <StatCard
                  title="Telegram Queue Depth"
                  value={d.queue_depth.telegram.toLocaleString('en-IN')}
                  status={d.queue_depth.telegram > 100 ? 'warning' : 'neutral'}
                />
                <StatCard
                  title="Email Queue Depth"
                  value={d.queue_depth.email.toLocaleString('en-IN')}
                  status={d.queue_depth.email > 100 ? 'warning' : 'neutral'}
                />
                <StatCard
                  title="Sent"
                  value={d.sent.toLocaleString('en-IN')}
                  status={d.sent > 0 ? 'healthy' : 'neutral'}
                  sub={`Last sent ${lastSentLabel}`}
                />
                <StatCard
                  title="Failed"
                  value={d.failed.toLocaleString('en-IN')}
                  status={d.failed > 0 ? 'critical' : 'neutral'}
                />
              </div>
              {/* Rate cap + deferred */}
              <div className={`grid grid-cols-2 gap-3 sm:${GRID_COLS_4}`}>
                <StatCard
                  title="Rate Capped"
                  value={d.rate_capped.toLocaleString('en-IN')}
                  status={d.rate_capped > 0 ? 'warning' : 'neutral'}
                />
                <StatCard
                  title="Deferred"
                  value={d.deferred.toLocaleString('en-IN')}
                  status={d.deferred > 0 ? 'warning' : 'neutral'}
                />
              </div>
            </>
          );
        })()}
      </section>

      {/* Section B — Template list */}
      <section aria-labelledby="section-templates">
        <Card>
          <CardHeader>
            <CardTitle id="section-templates">Notification Templates</CardTitle>
            <p className="mt-1 text-small text-ink-muted">
              In-code template IDs registered with the notification system.
            </p>
          </CardHeader>
          <CardBody>
            {healthQ.isLoading && <ListSkeleton rows={4} />}
            {healthQ.isError && (
              <ErrorCard title="Could not load templates" onRetry={() => healthQ.refetch()} />
            )}
            {healthQ.data && healthQ.data.templates.length === 0 && (
              <EmptyState
                title="No templates registered"
                description="Notification templates will appear here once defined in the codebase."
                className="py-8"
              />
            )}
            {healthQ.data && healthQ.data.templates.length > 0 && (
              <ul className="flex flex-col gap-1.5">
                {healthQ.data.templates.map((t) => (
                  <li
                    key={t.id}
                    className="flex items-center justify-between rounded-md border border-line bg-surface-2 px-4 py-2.5"
                  >
                    <span className="font-mono text-small text-ink">{t.id}</span>
                    <HealthBadge status="Healthy" />
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </section>

      {/* Section C — Broadcast composer (Phase 5 disabled affordance) */}
      <section aria-labelledby="section-broadcast">
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle id="section-broadcast">Broadcast Composer</CardTitle>
                <p className="mt-1 text-small text-ink-muted">
                  Send an announcement to all users. Audit-logged. Phase 5 — gated mutation.
                </p>
              </div>
              {/* broadcast_available indicator */}
              {healthQ.data && (
                <div className="shrink-0 flex flex-col items-end gap-1">
                  <span className="text-caption text-ink-muted">broadcast available</span>
                  <HealthBadge
                    status={healthQ.data.broadcast_available ? 'Healthy' : 'Paused'}
                  />
                </div>
              )}
            </div>
          </CardHeader>
          <CardBody>
            <div className="flex flex-col gap-4">
              {/* Disabled textarea — affordance only */}
              <div className="flex flex-col gap-2 opacity-40 pointer-events-none">
                <label className="text-small font-medium text-ink" htmlFor="broadcast-msg-disabled">
                  Message
                </label>
                <textarea
                  id="broadcast-msg-disabled"
                  rows={4}
                  disabled
                  placeholder="Broadcast message to all users…"
                  className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink resize-none placeholder:text-ink-faint focus:outline-none"
                />
              </div>
              <div className="flex items-center gap-3">
                <Button
                  size="sm"
                  variant="primary"
                  disabled
                  title="Broadcast composer — Phase 5 (gated mutation, audit-logged)"
                  className="opacity-40 cursor-not-allowed"
                >
                  Send Broadcast — Phase 5
                </Button>
                <p className="text-caption text-ink-faint">
                  Broadcast actions are a gated mutation requiring Phase 5 sign-off and
                  full Tier-B review + adversarial sign-off in the landing session.
                </p>
              </div>
            </div>
          </CardBody>
        </Card>
      </section>
    </div>
  );
}
