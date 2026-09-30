'use client';

/**
 * IdleSignOutModal — "Are you still there?" warning shown 1 minute before the
 * client-side idle sign-out fires (see frontend/src/lib/useIdleSignOut.ts).
 *
 * Accessibility contract (mirrors CommandPalette.tsx's focus-trap pattern):
 *  - role="dialog" aria-modal="true" aria-labelledby heading id
 *  - Focus trapped inside the dialog; Tab/Shift+Tab wrap
 *  - Escape = "Stay signed in" (never signs the user out on a stray Esc)
 *  - Focus moves to the primary "Stay signed in" button on open
 *
 * Mount once per logged-in shell (AppShell, AdminShell) — never on
 * public/auth pages, which have no session to protect.
 */

import * as React from 'react';
import { cn } from '@/lib/cn';
import { Button } from '@/components/ui/Button';
import { useIdleSignOut } from '@/lib/useIdleSignOut';

export function IdleSignOutModal() {
  const { open, stayActive, signOutNow } = useIdleSignOut();
  const dialogRef = React.useRef<HTMLDivElement>(null);
  const stayButtonRef = React.useRef<HTMLButtonElement>(null);
  const restoreFocusRef = React.useRef<HTMLElement | null>(null);

  React.useEffect(() => {
    if (!open) return;
    restoreFocusRef.current = document.activeElement as HTMLElement | null;
    requestAnimationFrame(() => stayButtonRef.current?.focus());
    return () => {
      restoreFocusRef.current?.focus?.();
    };
  }, [open]);

  React.useEffect(() => {
    if (!open) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        stayActive();
        return;
      }
      if (e.key === 'Tab') {
        const panel = dialogRef.current;
        if (!panel) return;
        const focusables = panel.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
        if (!focusables.length) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        const active = document.activeElement;
        if (e.shiftKey) {
          if (active === first || !panel.contains(active)) {
            e.preventDefault();
            last.focus();
          }
        } else if (active === last || !panel.contains(active)) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, stayActive]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" aria-hidden={!open}>
      <div className="absolute inset-0 bg-black/50" aria-hidden="true" />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="idle-signout-heading"
        className={cn(
          'relative z-10 w-full max-w-sm mx-4',
          'bg-surface border border-line rounded-lg shadow-lg',
          'flex flex-col gap-4 px-6 py-5',
        )}
      >
        <div className="flex flex-col gap-1">
          <h2 id="idle-signout-heading" className="text-h3 font-medium text-ink">
            Are you still there?
          </h2>
          <p className="text-small text-ink-secondary">
            For your safety, we&apos;ll sign you out in 1 minute because there has been no
            activity.
          </p>
        </div>
        <div className="flex items-center justify-end gap-3">
          <Button type="button" variant="ghost" size="md" onClick={signOutNow}>
            Sign out
          </Button>
          <Button
            ref={stayButtonRef}
            type="button"
            variant="primary"
            size="md"
            onClick={stayActive}
          >
            Stay signed in
          </Button>
        </div>
      </div>
    </div>
  );
}
