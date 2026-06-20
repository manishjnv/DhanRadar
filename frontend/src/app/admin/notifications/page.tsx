'use client';

/**
 * Admin Notifications — /admin/notifications
 * Tier-A (Admin.md §14 Notifications).
 *
 * Sections:
 *   A — Queue health KPIs (telegram depth · email depth · sent · failed · rate_capped · deferred · last_sent_at)
 *   B — Template list (template ids from the in-code list)
 *   C — Broadcast composer (Phase 5 live):
 *         form: title + body; channel fixed to telegram_public;
 *         explicit confirm checkbox + type-to-confirm "BROADCAST";
 *         Idempotency-Key = crypto.randomUUID() per submit, regenerated on Retry.
 *         Server errors advisory-language / quiet-hours / rate-limit surfaced clearly.
 *
 * Four-state contract: skeleton / empty / error+retry / data.
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
import { StatCard } from '@/components/admin/StatCard';
import { HealthBadge } from '@/components/admin/HealthBadge';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { formatRelative } from '@/components/admin/utils';
import { displayLabel } from '@/lib/displayLabel';
import { useAdminNotificationsHealth, useAdminBroadcast } from '@/features/admin/api';
import { ApiError } from '@/lib/apiClient';

// ---------------------------------------------------------------------------
// Idempotency key helper
// ---------------------------------------------------------------------------
function newIdempotencyKey() {
  return crypto.randomUUID();
}

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
// Known server error slugs for broadcast — surfaced with clear explanations.
// Returns a human-readable string; falls back to titleCase for unmapped slugs.
// ---------------------------------------------------------------------------
function broadcastErrorHint(detail: string): string {
  if (detail.includes('advisory_language') || detail.includes('advisory language')) {
    return 'The message may contain advisory language. Rephrase to educational language and retry.';
  }
  if (detail.includes('quiet_hours') || detail.includes('quiet hours')) {
    return 'Broadcast blocked by quiet hours policy. Retry during permitted send hours.';
  }
  if (detail.includes('rate_limit') || detail.includes('rate limit') || detail.includes('rate_capped')) {
    return 'Broadcast rate limit reached. Wait before retrying.';
  }
  // Unknown slug — render human-readable rather than raw.
  return displayLabel(detail);
}

// ---------------------------------------------------------------------------
// Broadcast composer section
// ---------------------------------------------------------------------------
function BroadcastComposer({ broadcastAvailable }: { broadcastAvailable: boolean }) {
  const broadcastMutation = useAdminBroadcast();

  const [open, setOpen] = React.useState(false);
  const [title, setTitle] = React.useState('');
  const [body, setBody] = React.useState('');
  const [acknowledged, setAcknowledged] = React.useState(false);
  const [idempotencyKey, setIdempotencyKey] = React.useState(newIdempotencyKey);

  function openComposer() {
    setTitle('');
    setBody('');
    setAcknowledged(false);
    setIdempotencyKey(newIdempotencyKey());
    setOpen(true);
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle id="section-broadcast">Broadcast Composer</CardTitle>
              <p className="mt-1 text-small text-ink-muted">
                Send an announcement to all users via Telegram public channel.
                Audit-logged. Rate-limited server-side. No advisory language.
              </p>
            </div>
            <div className="shrink-0 flex flex-col items-end gap-1">
              <span className="text-caption text-ink-muted">broadcast available</span>
              <HealthBadge status={broadcastAvailable ? 'Healthy' : 'Paused'} />
            </div>
          </div>
        </CardHeader>
        <CardBody>
          <Button
            size="sm"
            variant="secondary"
            onClick={openComposer}
            disabled={!broadcastAvailable}
            title={broadcastAvailable ? undefined : 'Broadcast is not available — check queue health'}
          >
            Compose Broadcast
          </Button>
          {!broadcastAvailable && (
            <p className="mt-2 text-caption text-amber">
              Broadcast channel is not configured — check the notification health before sending.
            </p>
          )}
        </CardBody>
      </Card>

      <ConfirmDialog
        open={open}
        onClose={() => setOpen(false)}
        title="Send broadcast"
        description={
          <>
            This will send a message to <strong>all users</strong> via Telegram public channel.
            The action is audit-logged and rate-limited. Advisory language (buy/sell/hold) will
            be rejected by the server. Type <strong>BROADCAST</strong> to confirm.
          </>
        }
        confirmLabel="Send Broadcast"
        confirmVariant="danger"
        confirmPhrase="BROADCAST"
        onConfirm={async () => {
          if (!title.trim()) throw new Error('Title is required.');
          if (!body.trim()) throw new Error('Message body is required.');
          if (!acknowledged) throw new Error('You must acknowledge the send warning.');
          try {
            await broadcastMutation.mutateAsync({
              payload: { title: title.trim(), body: body.trim(), channel: 'telegram_public' },
              idempotencyKey,
            });
          } catch (err) {
            // Regenerate idempotency key for retry
            setIdempotencyKey(newIdempotencyKey());
            if (err instanceof ApiError) {
              const detail = err.problem.detail ?? '';
              const hint = broadcastErrorHint(detail);
              throw new Error(hint || err.problem.title || 'Broadcast failed. Please retry.');
            }
            throw err;
          }
        }}
      >
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="broadcast-title" className="text-small font-medium text-ink">
              Title <span className="text-red">*</span>
            </label>
            <input
              id="broadcast-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Platform maintenance scheduled"
              className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-royal/40"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="broadcast-body" className="text-small font-medium text-ink">
              Message body <span className="text-red">*</span>
            </label>
            <textarea
              id="broadcast-body"
              rows={4}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Educational language only — no buy/sell/hold."
              className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink placeholder:text-ink-muted resize-y focus:outline-none focus:ring-2 focus:ring-royal/40"
            />
          </div>
          <div className="rounded-md border border-line bg-surface-2 px-3 py-2 text-caption text-ink-muted">
            Channel: <span className="font-mono">Public Telegram Channel</span> (fixed)
          </div>
          <label className="flex items-start gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(e) => setAcknowledged(e.target.checked)}
              className="mt-0.5 rounded border border-line accent-royal"
            />
            <span className="text-small text-ink-secondary">
              I confirm this message uses educational language only (no advisory verbs), and I understand
              it will be sent to all users and cannot be recalled.
            </span>
          </label>
        </div>
      </ConfirmDialog>
    </>
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
            Notification delivery status · templates · broadcast composer.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {healthQ.dataUpdatedAt > 0 && (
            <span className="text-caption text-ink-muted">
              Last updated {formatRelative(new Date(healthQ.dataUpdatedAt).toISOString())}
            </span>
          )}
          <Button variant="ghost" size="sm" onClick={() => healthQ.refetch()}>
            <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
            Refresh
          </Button>
        </div>
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
                <div className="flex flex-col gap-1">
                  <StatCard
                    title="Rate Capped"
                    value={d.rate_capped.toLocaleString('en-IN')}
                    status={d.rate_capped > 0 ? 'warning' : 'neutral'}
                  />
                  <p className="text-caption text-ink-muted">
                    Held because the daily broadcast limit was reached.
                  </p>
                </div>
                <div className="flex flex-col gap-1">
                  <StatCard
                    title="Deferred"
                    value={d.deferred.toLocaleString('en-IN')}
                    status={d.deferred > 0 ? 'warning' : 'neutral'}
                  />
                  <p className="text-caption text-ink-muted">
                    Held by quiet-hours policy.
                  </p>
                </div>
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

      {/* Section C — Broadcast composer.
          Shown even when the health query failed so the composer remains
          accessible; broadcast_available defaults to false in that case. */}
      <section aria-labelledby="section-broadcast">
        {healthQ.isLoading && <Skeleton className="h-32 rounded-xl" />}
        {!healthQ.isLoading && (
          <BroadcastComposer
            broadcastAvailable={healthQ.data?.broadcast_available ?? false}
          />
        )}
        {healthQ.isError && (
          <p className="mt-2 text-caption text-amber">
            Queue health could not be loaded — broadcast is disabled until health status is confirmed.
          </p>
        )}
      </section>
    </div>
  );
}
