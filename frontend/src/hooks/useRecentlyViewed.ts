'use client';

/**
 * Recently Viewed — localStorage ring buffer (WATCHLIST_LIVE_DATA_PLAN.md
 * Wave 2 item "S13 Recently Viewed").
 *
 * Fund detail pushes {isin, name, at} on view; the watchlist page reads the
 * list. Cap 10, most-recent-first, de-duped by ISIN (re-viewing a fund moves
 * it back to the front rather than creating a second entry).
 *
 * Hydration-safe, same pattern as `hooks/useWatchlist.ts`: [] on the server
 * and first client render, the real list only after mount.
 */

import * as React from 'react';

export interface RecentlyViewedEntry {
  isin: string;
  name: string;
  /** ISO datetime of the view. */
  at: string;
}

const KEY = 'dr.recently-viewed.v1';
const EVT = 'dr-recently-viewed-change';
const CAP = 10;

function read(): RecentlyViewedEntry[] {
  if (typeof window === 'undefined') return [];
  try {
    const list = JSON.parse(window.localStorage.getItem(KEY) ?? '[]');
    return Array.isArray(list) ? list.filter((e) => e && typeof e.isin === 'string') : [];
  } catch {
    return [];
  }
}

function write(list: RecentlyViewedEntry[]) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    // quota exceeded / private mode — the in-page state still updates this session
  }
  window.dispatchEvent(new Event(EVT));
}

/** Push a fund view onto the ring buffer. Call from the fund detail page on view. */
export function pushRecentlyViewed(isin: string, name: string): void {
  if (typeof window === 'undefined') return;
  const cur = read().filter((e) => e.isin !== isin);
  write([{ isin, name, at: new Date().toISOString() }, ...cur].slice(0, CAP));
}

/** Hydration-safe: [] on the server and first client render, real list after mount. */
export function useRecentlyViewed(): RecentlyViewedEntry[] {
  const [list, setList] = React.useState<RecentlyViewedEntry[]>([]);

  React.useEffect(() => {
    const sync = () => setList(read());
    sync();
    window.addEventListener(EVT, sync); // same-tab writes
    window.addEventListener('storage', sync); // other tabs
    return () => {
      window.removeEventListener(EVT, sync);
      window.removeEventListener('storage', sync);
    };
  }, []);

  return list;
}
