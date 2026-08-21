'use client';

/**
 * Admin Feature Flags — /admin/flags
 * Tier-A read-only page.
 *
 * Displays the current flag list (Name · Description · Value · Source).
 * All toggle controls are DISABLED — flags are env-driven; changes require
 * a config update and container restart (not a UI mutation).
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
import { useAdminFlags, type AdminFlag } from '@/features/admin/api';
import { cn } from '@/lib/cn';
import { displayLabel } from '@/lib/displayLabel';
import { formatRelative } from '@/components/admin/utils';

// Per-flag help text: what on/off means in plain words.
const FLAG_HELP: Record<string, string> = {
  AUDIT_ARCHIVE_ENABLED: 'On: audit records are archived daily. Off: archiving is paused.',
  COOKIE_SECURE: 'On: session cookies require HTTPS. Off: cookies are sent over any connection (development only).',
  DPDP_CONSENT_ENFORCED: 'On: data-processing routes require active user consent. Off: consent checks are skipped.',
};

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------
function TableSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2">
      {[...Array(rows)].map((_, i) => (
        <Skeleton key={i} className="h-11 rounded-md" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Value badge — on / off pill
// ---------------------------------------------------------------------------
function ValueBadge({ value }: { value: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-caption font-medium',
        value
          ? 'bg-emerald/10 text-emerald'
          : 'bg-surface-2 text-ink-muted border border-line',
      )}
    >
      {value ? 'on' : 'off'}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Flags table
// ---------------------------------------------------------------------------
function FlagsTable({ flags }: { flags: AdminFlag[] }) {
  if (flags.length === 0) {
    return (
      <EmptyState
        title="No feature flags"
        description="Feature flag configuration will appear here once flags are defined in the running config."
        className="py-12"
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <caption className="sr-only">Feature flags from the running server config</caption>
        <thead>
          <tr className="border-b border-line">
            <th scope="col" className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">Name</th>
            <th scope="col" className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">Description</th>
            <th scope="col" className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">Value</th>
            <th scope="col" className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">Source</th>
            {/* Read-only switch column */}
            <th scope="col" className="pb-2 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {flags.map((flag) => {
            const humanName = displayLabel(flag.key, 'flag');
            const helpText = FLAG_HELP[flag.key];
            const sourceLabel = flag.source === 'env'
              ? 'Set via server config (restart to change)'
              : flag.source;
            return (
              <tr
                key={flag.key}
                className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors"
              >
                <td className="py-3 pr-4 whitespace-nowrap">
                  <span className="text-small font-medium text-ink">{humanName}</span>
                  <span
                    className="block font-mono text-[10px] text-ink-faint mt-0.5"
                    title={flag.key}
                  >
                    {flag.key}
                  </span>
                </td>
                <td className="py-3 pr-4 text-small text-ink-secondary max-w-xs">
                  <span>{flag.description || '—'}</span>
                  {helpText && (
                    <span className="block mt-0.5 text-caption text-ink-muted">{helpText}</span>
                  )}
                </td>
                <td className="py-3 pr-4">
                  <ValueBadge value={flag.value} />
                </td>
                <td className="py-3 pr-4 text-caption text-ink-muted">
                  {sourceLabel}
                </td>
                <td className="py-3">
                  {/* Always disabled — env-driven */}
                  <button
                    disabled
                    title="Set via server config — change via config file and restart the container"
                    className={cn(
                      'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
                      'cursor-not-allowed opacity-40',
                      flag.value ? 'bg-emerald/40' : 'bg-surface-2 border border-line',
                    )}
                    aria-checked={flag.value}
                    role="switch"
                    aria-disabled="true"
                  >
                    <span
                      className={cn(
                        'inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow-sm transition-transform',
                        flag.value ? 'translate-x-4' : 'translate-x-0.5',
                      )}
                    />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// UI section coverage — static build-tracker (measured from frontend code,
// not derivable from any API). Re-measure and update when a page's sections
// get wired to live data. Census method: top-level sections per page,
// "live" = fed by a features/*/api hook, apiClient, or /api/v1 fetch.
// ---------------------------------------------------------------------------
const COVERAGE_AS_OF = '21 Aug 2026';

type PageCoverage = {
  page: string;
  route: string;
  total: number;
  live: number;
  pending: string; // sections still on sample/static data, plain words
  byDesign?: boolean; // static on purpose — not a gap
};

const UI_COVERAGE: PageCoverage[] = [
  { page: 'Watchlist', route: '/mf/watchlist', total: 15, live: 13, pending: 'Discover More and FAQ (static by design)' },
  { page: 'Fund Compare', route: '/mf/compare', total: 21, live: 18, pending: 'EduRead + AI Insights (C3 AI wave); FAQ (static by design)' },
  { page: 'Pricing', route: '/pricing', total: 4, live: 1, pending: 'Hero, comparison table, FAQ (plans list is live)' },
  { page: 'Portfolio', route: '/mf/portfolio', total: 23, live: 6, pending: 'Health, goals, overlap, cost, AMC, timeline, projections, AI, report + 8 more' },
  { page: 'Fund Explorer', route: '/mf/explore', total: 16, live: 5, pending: 'AI discovery, category leaderboards, fund flow, momentum, consistency, low-cost, beginner picks, AI feed, shortlist, filters, FAQ' },
  { page: 'Signal', route: '/signal', total: 13, live: 12, pending: '"How Signal works" explainer copy' },
  { page: 'Leaderboard', route: '/mf/leaderboard', total: 16, live: 15, pending: 'FAQ copy' },
  { page: 'Fund Detail', route: '/mf/fund/[isin]', total: 22, live: 21, pending: 'Entry-timing explainer' },
  { page: 'Invest (BSE UAT)', route: '/mf/invest/[isin]', total: 1, live: 1, pending: '—' },
  { page: 'Market Mood', route: '/mood', total: 8, live: 8, pending: '—' },
  { page: 'Learn', route: '/learn', total: 2, live: 2, pending: '—' },
  { page: 'Settings', route: '/settings/*', total: 4, live: 4, pending: '—' },
  { page: 'Calculators', route: '/calculators', total: 7, live: 0, pending: 'Pure client-side engines — no backend needed', byDesign: true },
  { page: 'Landing', route: '/', total: 5, live: 0, pending: 'Marketing copy — static on purpose', byDesign: true },
];

function CoverageBadge({ pct, byDesign }: { pct: number; byDesign?: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-caption font-medium tabular-nums',
        byDesign
          ? 'bg-surface-2 text-ink-muted border border-line'
          : pct >= 90
            ? 'bg-emerald/10 text-emerald'
            : pct >= 50
              ? 'bg-royal/10 text-royal'
              : 'bg-amber/10 text-amber',
      )}
    >
      {byDesign ? 'by design' : `${pct}%`}
    </span>
  );
}

function UiCoverageTable() {
  const rows = [...UI_COVERAGE].sort((a, b) => {
    if (!!a.byDesign !== !!b.byDesign) return a.byDesign ? 1 : -1;
    return a.live / a.total - b.live / b.total;
  });
  const tracked = UI_COVERAGE.filter((r) => !r.byDesign);
  const totalSections = tracked.reduce((s, r) => s + r.total, 0);
  const totalLive = tracked.reduce((s, r) => s + r.live, 0);

  return (
    <section aria-labelledby="section-ui-coverage">
      <Card>
        <CardHeader>
          <CardTitle id="section-ui-coverage">UI Section Coverage</CardTitle>
          <p className="mt-1 text-small text-ink-muted">
            How many sections on each page show live data versus sample or placeholder content.
            Measured from the frontend code on {COVERAGE_AS_OF} — {totalLive} of {totalSections} tracked
            sections are live. Update this list when a page gets wired up.
          </p>
        </CardHeader>
        <CardBody>
          <div className="overflow-x-auto">
            <table className="w-full text-small">
              <caption className="sr-only">Per-page count of UI sections fed by live backend data</caption>
              <thead>
                <tr className="border-b border-line">
                  <th scope="col" className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">Page</th>
                  <th scope="col" className="pb-2 pr-4 text-right text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">Sections</th>
                  <th scope="col" className="pb-2 pr-4 text-right text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">Live</th>
                  <th scope="col" className="pb-2 pr-4 text-right text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">Needs data</th>
                  <th scope="col" className="pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">Waiting on live data</th>
                  <th scope="col" className="pb-2 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono">Coverage</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.route} className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors">
                    <td className="py-3 pr-4 whitespace-nowrap">
                      <span className="text-small font-medium text-ink">{r.page}</span>
                      <span className="block font-mono text-[10px] text-ink-faint mt-0.5">{r.route}</span>
                    </td>
                    <td className="py-3 pr-4 text-right tabular-nums text-ink-secondary">{r.total}</td>
                    <td className="py-3 pr-4 text-right tabular-nums text-ink-secondary">{r.live}</td>
                    <td className="py-3 pr-4 text-right tabular-nums font-medium text-ink">
                      {r.byDesign ? '—' : r.total - r.live}
                    </td>
                    <td className="py-3 pr-4 text-caption text-ink-muted max-w-md">{r.pending}</td>
                    <td className="py-3">
                      <CoverageBadge pct={Math.round((r.live / r.total) * 100)} byDesign={r.byDesign} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Flags page
// ---------------------------------------------------------------------------
export default function AdminFlagsPage() {
  const flagsQ = useAdminFlags();

  return (
    <div className="flex flex-col gap-8">
      {/* Page header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-h2 font-medium text-ink">Feature Flags</h1>
          <p className="mt-1 text-small text-ink-muted">
            Read-only view of current feature flags from the running config. Toggles are disabled —
            flags are set via server config and require a container restart to change.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {flagsQ.dataUpdatedAt > 0 && (
            <span className="text-caption text-ink-muted">
              Last updated {formatRelative(new Date(flagsQ.dataUpdatedAt).toISOString())}
            </span>
          )}
          <Button variant="ghost" size="sm" onClick={() => flagsQ.refetch()}>
            <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Info note */}
      <div className="rounded-lg border border-amber/30 bg-amber/5 px-5 py-3">
        <p className="text-small text-amber">
          These flags are read-only here and change only via server config.
        </p>
      </div>

      {/* Flags table */}
      <section aria-labelledby="section-flags-table">
        <Card>
          <CardHeader>
            <CardTitle id="section-flags-table">Flag List</CardTitle>
            <p className="mt-1 text-small text-ink-muted">
              Name · Description · Current value · Source.
            </p>
          </CardHeader>
          <CardBody>
            {flagsQ.isLoading && <TableSkeleton rows={8} />}
            {flagsQ.isError && (
              <ErrorCard
                title="Could not load feature flags"
                onRetry={() => flagsQ.refetch()}
              />
            )}
            {flagsQ.data && <FlagsTable flags={flagsQ.data} />}
          </CardBody>
        </Card>
      </section>

      {/* UI section coverage — static build tracker */}
      <UiCoverageTable />
    </div>
  );
}
