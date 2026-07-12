'use client';

/**
 * Watchlist store — localStorage-backed (V1.5: real per-browser persistence).
 *
 * The fund-detail hero star and the /mf/watchlist page share this one store.
 * ponytail: per-browser localStorage; move to a backend table when accounts
 * need cross-device sync (the "real watchlist pipeline" session).
 */

import * as React from 'react';

export interface WatchlistEntry {
  isin: string;
  name: string;
  category: string | null;
  addedAt: string;
}

const KEY = 'dr.watchlist.v1';
const EVT = 'dr-watchlist-change';

function read(): WatchlistEntry[] {
  if (typeof window === 'undefined') return [];
  try {
    const list = JSON.parse(window.localStorage.getItem(KEY) ?? '[]');
    return Array.isArray(list) ? list.filter((e) => e && typeof e.isin === 'string') : [];
  } catch {
    return [];
  }
}

function write(list: WatchlistEntry[]) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    // quota exceeded / private mode — the in-page toggle still works this session
  }
  window.dispatchEvent(new Event(EVT));
}

/** Hydration-safe: [] on the server and first client render, real list after mount. */
export function useWatchlist() {
  const [list, setList] = React.useState<WatchlistEntry[]>([]);

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

  const has = React.useCallback((isin: string) => list.some((e) => e.isin === isin), [list]);

  const toggle = React.useCallback((entry: Omit<WatchlistEntry, 'addedAt'>) => {
    const cur = read();
    write(
      cur.some((e) => e.isin === entry.isin)
        ? cur.filter((e) => e.isin !== entry.isin)
        : [...cur, { ...entry, addedAt: new Date().toISOString() }],
    );
  }, []);

  return { list, has, toggle };
}
