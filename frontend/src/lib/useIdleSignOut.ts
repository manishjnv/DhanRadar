'use client';

/**
 * useIdleSignOut — 15-minute client-side idle sign-out.
 *
 * Pairs with the server-side hard idle cutoff (SESSION_IDLE_TIMEOUT_MIN=20,
 * backend/dhanradar/auth/service.py) which is the enforcement backstop; this
 * hook is the UX layer that warns the user and signs them out before that.
 *
 * Behaviour:
 *  - Tracks pointerdown / keydown / scroll / touchstart, throttled to ~1/s.
 *  - Activity is written to localStorage so ANY open tab resetting the clock
 *    resets it for every tab (cross-tab via the `storage` event); falls back
 *    to in-memory only if localStorage throws (private mode, blocked, etc.).
 *  - At WARN_AT_MS idle, IdleSignOutModal shows "Are you still there?".
 *  - At IDLE_SIGNOUT_MS idle, POSTs /auth/logout (best-effort) and redirects
 *    to /login?reason=idle.
 *  - Keep-alive: on activity, if the last successful refresh was
 *    >= KEEPALIVE_MS ago, calls apiClient's single-flight tryRefresh() so a
 *    still-active user's session never silently lapses mid-use. No second
 *    refresh implementation is written here.
 *
 * Mount ONE <IdleSignOutModal /> per logged-in shell (AppShell, AdminShell).
 * Never mount on public/auth pages — there is no session to protect there.
 */

import * as React from 'react';
import { api, tryRefresh } from '@/lib/apiClient';

export const IDLE_SIGNOUT_MS = 15 * 60 * 1000;
export const WARN_AT_MS = 14 * 60 * 1000;
export const KEEPALIVE_MS = 5 * 60 * 1000;
const CHECK_INTERVAL_MS = 15 * 1000;
const ACTIVITY_THROTTLE_MS = 1000;

export const STORAGE_KEY = 'dr:lastActivity';

const ACTIVITY_EVENTS = ['pointerdown', 'keydown', 'scroll', 'touchstart'] as const;

function readStoredActivity(): number | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  } catch {
    return null; // ponytail: localStorage can throw (private mode) — in-memory fallback covers it
  }
}

function writeStoredActivity(ts: number): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, String(ts));
  } catch {
    // best-effort only — the in-memory ref is still updated by the caller
  }
}

export interface UseIdleSignOutResult {
  /** True once WARN_AT_MS of inactivity has elapsed and sign-out hasn't fired yet. */
  open: boolean;
  /** "Stay signed in" — records activity now and refreshes the session. */
  stayActive: () => void;
  /** "Sign out" — same path as the automatic idle timeout. */
  signOutNow: () => void;
}

export function useIdleSignOut(): UseIdleSignOutResult {
  const [open, setOpen] = React.useState(false);
  const lastActivityRef = React.useRef<number>(Date.now());
  const lastRefreshRef = React.useRef<number>(Date.now());
  const signedOutRef = React.useRef(false);

  const doSignOut = React.useCallback(() => {
    if (signedOutRef.current) return;
    signedOutRef.current = true;
    // Best-effort — a failed logout call must not block the redirect; the
    // server-side idle window (SESSION_IDLE_TIMEOUT_MIN) closes the session
    // regardless within a few minutes even if this call is lost.
    api.post('/auth/logout').catch(() => {});
    window.location.assign('/login?reason=idle');
  }, []);

  const recordActivity = React.useCallback((ts: number) => {
    lastActivityRef.current = ts;
    writeStoredActivity(ts);
    setOpen(false);
  }, []);

  const stayActive = React.useCallback(() => {
    const now = Date.now();
    recordActivity(now);
    lastRefreshRef.current = now;
    void tryRefresh();
  }, [recordActivity]);

  const signOutNow = React.useCallback(() => {
    doSignOut();
  }, [doSignOut]);

  React.useEffect(() => {
    if (typeof window === 'undefined') return;

    // Seed from any other tab's more-recent activity on mount.
    const stored = readStoredActivity();
    if (stored !== null && stored > lastActivityRef.current) {
      lastActivityRef.current = stored;
    }

    let lastHandled = 0;
    function onActivity() {
      const now = Date.now();
      if (now - lastHandled < ACTIVITY_THROTTLE_MS) return;
      lastHandled = now;
      recordActivity(now);
      if (now - lastRefreshRef.current >= KEEPALIVE_MS) {
        lastRefreshRef.current = now;
        void tryRefresh();
      }
    }

    function onStorage(e: StorageEvent) {
      if (e.key !== STORAGE_KEY || !e.newValue) return;
      const ts = Number(e.newValue);
      if (Number.isFinite(ts) && ts > lastActivityRef.current) {
        lastActivityRef.current = ts;
        setOpen(false);
      }
    }

    for (const evt of ACTIVITY_EVENTS) {
      window.addEventListener(evt, onActivity, { passive: true });
    }
    window.addEventListener('storage', onStorage);

    const interval = setInterval(() => {
      const idleFor = Date.now() - lastActivityRef.current;
      if (idleFor >= IDLE_SIGNOUT_MS) {
        doSignOut();
      } else if (idleFor >= WARN_AT_MS) {
        setOpen(true);
      }
    }, CHECK_INTERVAL_MS);

    return () => {
      for (const evt of ACTIVITY_EVENTS) {
        window.removeEventListener(evt, onActivity);
      }
      window.removeEventListener('storage', onStorage);
      clearInterval(interval);
    };
  }, [recordActivity, doSignOut]);

  return { open, stayActive, signOutNow };
}
