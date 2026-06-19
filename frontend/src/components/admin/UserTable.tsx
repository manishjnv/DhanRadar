'use client';

/**
 * UserTable — compact table of admin user rows.
 *
 * Columns: Name · Email · Plan (tier) · Status · Last Login · Joined · Actions
 * Actions:
 *   [View]          — always live
 *   [Suspend]       — Phase 5: ConfirmDialog with type-to-confirm email + reason field
 *   [Unsuspend]     — Phase 5: simple ConfirmDialog
 *   [Reset Access]  — Phase 5: ConfirmDialog with type-to-confirm email + reset-session warning
 * No advisory verbs. Numeric values allowed (admin-only, Admin.md §16).
 */

import * as React from 'react';
import { HealthBadge } from './HealthBadge';
import { ConfirmDialog } from './ConfirmDialog';
import { Button } from '@/components/ui/Button';
import { formatRelative, formatDateTime } from './utils';
import { cn } from '@/lib/cn';
import {
  useSuspendUser,
  useUnsuspendUser,
  useResetUserAccess,
  type AdminUserRow,
} from '@/features/admin/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface UserTableProps {
  users: AdminUserRow[];
  onView: (userId: string) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Per-row action dialog state
// ---------------------------------------------------------------------------
type ActionKind = 'suspend' | 'unsuspend' | 'reset-access' | null;

interface ActiveAction {
  user: AdminUserRow;
  kind: ActionKind;
}

// ---------------------------------------------------------------------------
// UserTable
// ---------------------------------------------------------------------------
export function UserTable({ users, onView }: UserTableProps) {
  const suspendMutation      = useSuspendUser();
  const unsuspendMutation    = useUnsuspendUser();
  const resetAccessMutation  = useResetUserAccess();

  const [activeAction, setActiveAction] = React.useState<ActiveAction>({ user: users[0] ?? ({} as AdminUserRow), kind: null });
  const [suspendReason, setSuspendReason] = React.useState('');

  function openDialog(user: AdminUserRow, kind: Exclude<ActionKind, null>) {
    setSuspendReason('');
    setActiveAction({ user, kind });
  }
  function closeDialog() {
    setActiveAction((prev) => ({ ...prev, kind: null }));
  }

  const activeUser = activeAction.user;

  return (
    <>
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
                    {user.status === 'suspended' ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => openDialog(user, 'unsuspend')}
                      >
                        Unsuspend
                      </Button>
                    ) : user.status === 'active' ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => openDialog(user, 'suspend')}
                      >
                        Suspend
                      </Button>
                    ) : null}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => openDialog(user, 'reset-access')}
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

      {/* Suspend dialog — type-to-confirm email */}
      <ConfirmDialog
        open={activeAction.kind === 'suspend'}
        onClose={closeDialog}
        title="Suspend user"
        description={
          <>
            The user <strong>{activeUser.email}</strong> will lose all access until manually unsuspended.
            Active sessions will remain valid until they expire (no forced revocation).
            Enter a reason and type the user&apos;s email to confirm.
          </>
        }
        confirmLabel="Suspend"
        confirmVariant="danger"
        confirmPhrase={activeUser.email}
        onConfirm={async () => {
          await suspendMutation.mutateAsync({ id: activeUser.id, reason: suspendReason || undefined });
        }}
      >
        {/* Reason field */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="suspend-reason" className="text-small font-medium text-ink">
            Reason <span className="text-ink-muted font-normal">(optional)</span>
          </label>
          <input
            id="suspend-reason"
            type="text"
            value={suspendReason}
            onChange={(e) => setSuspendReason(e.target.value)}
            placeholder="e.g. Terms of service violation"
            className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-royal/40"
          />
        </div>
      </ConfirmDialog>

      {/* Unsuspend dialog — simple confirm */}
      <ConfirmDialog
        open={activeAction.kind === 'unsuspend'}
        onClose={closeDialog}
        title="Unsuspend user"
        description={
          <>
            <strong>{activeUser.email}</strong> will regain normal access to their account.
          </>
        }
        confirmLabel="Unsuspend"
        confirmVariant="primary"
        onConfirm={async () => {
          await unsuspendMutation.mutateAsync(activeUser.id);
        }}
      />

      {/* Reset Access dialog — type-to-confirm email */}
      <ConfirmDialog
        open={activeAction.kind === 'reset-access'}
        onClose={closeDialog}
        title="Reset user access"
        description={
          <>
            This will reset any manual access grants for <strong>{activeUser.email}</strong>.
            Note: this does <strong>not</strong> revoke active sessions — the user remains
            logged in until their current JWT expires. Type the user&apos;s email to confirm.
          </>
        }
        confirmLabel="Reset Access"
        confirmVariant="danger"
        confirmPhrase={activeUser.email}
        onConfirm={async () => {
          await resetAccessMutation.mutateAsync(activeUser.id);
        }}
      />
    </>
  );
}
