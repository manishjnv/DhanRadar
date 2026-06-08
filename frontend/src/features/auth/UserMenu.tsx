'use client';

/**
 * UserMenu — topbar identity + logout. Composed into AppShell by the (app)
 * layout so the shared shell stays presentation-only and never imports a
 * feature itself.
 */

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import { useMe, useLogout } from './api';

function initials(email: string): string {
  const name = email.split('@')[0] ?? '';
  const parts = name.split(/[._-]+/).filter(Boolean);
  const chars = parts.length >= 2 ? parts[0][0] + parts[1][0] : name.slice(0, 2);
  return chars.toUpperCase() || '?';
}

export function UserMenu() {
  const router = useRouter();
  const { data: user } = useMe();
  const { mutate: logout, isPending } = useLogout();

  if (!user) return null;

  function handleLogout() {
    logout(undefined, {
      onSettled: () => router.replace('/login'),
    });
  }

  return (
    <div className="flex items-center gap-3">
      <span className="hidden text-small text-ink-secondary sm:inline" title={user.email}>
        {user.email}
      </span>
      <div
        className="flex h-8 w-8 items-center justify-center rounded-full bg-royal/10 text-caption font-medium text-royal"
        aria-hidden="true"
      >
        {initials(user.email)}
      </div>
      <Button variant="ghost" size="sm" onClick={handleLogout} disabled={isPending}>
        {isPending ? 'Signing out…' : 'Log out'}
      </Button>
    </div>
  );
}
