'use client';

/**
 * UserTable — compact table of admin user rows.
 *
 * Columns: Name · Email · Plan (tier) · Status · Last Login · Joined · Actions
 * Actions: [View] always live; [Suspend] [Upgrade] [Reset Access] rendered disabled (Phase 5).
 * No advisory verbs. Numeric values allowed (admin-only, Admin.md §16).
 */

import * as React from 'react';
import { HealthBadge } from './HealthBadge';
import { Button } from '@/components/ui/Button';
import { formatRelative, formatDateTime } from './utils';
import { cn } from '@/lib/cn';
import type { AdminUserRow } from '@/features/admin/api';

interface UserTableProps {
  users: AdminUserRow[];
  onView: (userId: string) => void;
}

function tierBadgeClass(tier: string): string {
  if (tier === 'plus' || tier === 'founder_lifetime') {
    return 'bg-emerald/10 text-emerald';
  }
  if (tier === 'trial') {
    return 'bg-amber/10 text-amber';
  }
  return 'bg-surface-2 text-ink-muted';
}

const HEADERS = ['Name', 'Email', 'Plan', 'Status', 'Last Login', 'Joined', ''];

export function UserTable({ users, onView }: UserTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <thead>
          <tr className="border-b border-line">
            {HEADERS.map((h) => (
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
          {users.map((user) => (
            <tr
              key={user.id}
              className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors"
            >
              {/* Name */}
              <td className="py-2.5 pr-4 font-medium text-ink whitespace-nowrap">
                {user.display_name || '—'}
              </td>
              {/* Email */}
              <td className="py-2.5 pr-4 text-ink-secondary text-[11px]">
                {user.email}
              </td>
              {/* Plan / tier */}
              <td className="py-2.5 pr-4">
                <span
                  className={cn(
                    'rounded-full px-2 py-0.5 text-caption font-medium',
                    tierBadgeClass(user.tier),
                  )}
                >
                  {user.tier}
                </span>
              </td>
              {/* Status */}
              <td className="py-2.5 pr-4">
                <HealthBadge
                  status={
                    user.status === 'active'    ? 'Healthy'  :
                    user.status === 'suspended' ? 'Failed'   :
                    user.status === 'blocked'   ? 'Critical' :
                    'Paused'
                  }
                />
              </td>
              {/* Last Login */}
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                {user.last_login_at ? formatRelative(user.last_login_at) : '—'}
              </td>
              {/* Joined */}
              <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-muted">
                {formatDateTime(user.created_at)}
              </td>
              {/* Actions */}
              <td className="py-2.5">
                <div className="flex items-center gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onView(user.id)}
                  >
                    View
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled
                    title="Phase 5 — gated mutation"
                    className="opacity-40 cursor-not-allowed"
                  >
                    Suspend
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled
                    title="Phase 5 — gated mutation"
                    className="opacity-40 cursor-not-allowed"
                  >
                    Upgrade
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled
                    title="Phase 5 — gated mutation"
                    className="opacity-40 cursor-not-allowed"
                  >
                    Reset Access
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
