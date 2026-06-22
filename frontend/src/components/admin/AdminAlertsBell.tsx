'use client';

/**
 * AdminAlertsBell — top-bar attention bell, ADMIN-ONLY.
 *
 * Lives in components/ (not features/) so it may compose useMe + the admin api —
 * a feature cannot import another feature's internals, but a shared component can.
 * Self-contained: reads `is_admin` from useMe and renders nothing for non-admins
 * (so a non-admin never fires the 404-on-non-admin /admin/alerts request). Shows a
 * count badge and a dropdown of derived health alerts (stale mood snapshot, degraded
 * mood, ingestion failures, unreachable sources). Read-only; numbers are allowed on
 * the admin surface (Admin.md §16) — this is not a public score.
 */

import * as React from 'react';
import Link from 'next/link';
import { Bell } from 'lucide-react';
import { useMe } from '@/features/auth/api';
import { useAdminAlerts } from '@/features/admin/api';

const SEV_COLOR: Record<string, string> = {
  critical: '#ef4444',
  warning: '#f59e0b',
  info: '#2563eb',
};

export function AdminAlertsBell() {
  const { data: me } = useMe();
  const isAdmin = me?.is_admin === true;
  const [open, setOpen] = React.useState(false);
  const { data } = useAdminAlerts(isAdmin);

  if (!isAdmin) return null;

  const count = data?.count ?? 0;
  const alerts = data?.alerts ?? [];

  return (
    <div className="relative">
      <button
        type="button"
        aria-label={count ? `Admin alerts (${count} need attention)` : 'Admin alerts'}
        onClick={() => setOpen((o) => !o)}
        className="relative grid h-9 w-9 place-items-center rounded-md text-ink-secondary transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
      >
        <Bell size={18} aria-hidden="true" />
        {count > 0 && (
          <span
            className="absolute -right-0.5 -top-0.5 grid h-4 min-w-[16px] place-items-center rounded-full px-1 text-[10px] font-bold leading-none text-white"
            style={{ background: '#ef4444' }}
          >
            {count > 9 ? '9+' : count}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden="true" />
          <div className="absolute right-0 z-50 mt-2 w-80 overflow-hidden rounded-lg border border-line bg-surface shadow-lg">
            <div className="border-b border-line px-4 py-3 text-small font-medium text-ink">
              Needs attention
              {count > 0 && <span className="text-ink-muted"> ({count})</span>}
            </div>
            <div className="max-h-96 overflow-y-auto">
              {alerts.length === 0 ? (
                <p className="px-4 py-6 text-center text-small text-ink-muted">
                  All clear — nothing needs attention.
                </p>
              ) : (
                alerts.map((a) => (
                  <Link
                    key={a.key}
                    href={a.href ?? '/admin'}
                    onClick={() => setOpen(false)}
                    className="flex gap-3 border-b border-line px-4 py-3 last:border-0 hover:bg-surface-2"
                  >
                    <span
                      className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                      style={{ background: SEV_COLOR[a.severity] ?? '#64748b' }}
                      aria-hidden="true"
                    />
                    <span className="min-w-0">
                      <span className="block text-small font-medium text-ink">{a.title}</span>
                      <span className="mt-0.5 block text-caption text-ink-muted">{a.detail}</span>
                    </span>
                  </Link>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default AdminAlertsBell;
