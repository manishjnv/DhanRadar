'use client';

/**
 * Watchlist store — dual-mode facade.
 *
 * Anonymous: localStorage (per-browser). Logged in: the mf.mf_watchlist_items
 * backend (GET/PUT/DELETE /mf/watchlist) is the source of truth, and any
 * localStorage entries are merged UP once, then cleared — so a star set before
 * signing up survives login and syncs across devices.
 *
 * The fund-detail hero star and the /mf/watchlist page share this one store;
 * both consume the same { list, has, toggle } shape in either mode.
 */

import * as React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import { useMe } from '@/features/auth/api';

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

interface WatchlistApiResponse {
  items: { isin: string; created_at: string }[];
}

/** Hydration-safe: [] on the server and first client render, real list after mount. */
export function useWatchlist() {
  const qc = useQueryClient();
  const { data: user } = useMe();
  const [list, setList] = React.useState<WatchlistEntry[]>([]);
  const mergedRef = React.useRef(false);

  const serverQuery = useQuery<WatchlistEntry[]>({
    queryKey: queryKeys.mf.watchlist(),
    queryFn: async () => {
      const res = await api.get<WatchlistApiResponse>('/mf/watchlist');
      return res.items.map((item) => ({
        isin: item.isin,
        name: '',
        category: null,
        addedAt: item.created_at,
      }));
    },
    enabled: !!user,
    staleTime: 60 * 1000,
  });

  React.useEffect(() => {
    if (user) {
      setList(serverQuery.data ?? []);
    } else {
      setList(read());
    }
  }, [user, serverQuery.data]);

  React.useEffect(() => {
    const sync = () => {
      if (!user) setList(read());
    };
    sync();
    window.addEventListener(EVT, sync); // same-tab writes
    window.addEventListener('storage', sync); // other tabs
    return () => {
      window.removeEventListener(EVT, sync);
      window.removeEventListener('storage', sync);
    };
  }, [user]);

  // One-time merge-up: pre-login stars move to the account on first
  // authenticated mount. On any PUT failure the local copy is kept.
  React.useEffect(() => {
    if (!user || mergedRef.current) return;
    mergedRef.current = true;

    const local = read();
    if (local.length === 0) return;

    (async () => {
      let failed = false;
      for (const entry of local) {
        try {
          await api.put<void>(`/mf/watchlist/${entry.isin}`);
        } catch {
          failed = true;
        }
      }
      if (!failed) {
        write([]);
        qc.invalidateQueries({ queryKey: queryKeys.mf.watchlist() });
      }
    })();
  }, [user, qc]);

  const has = React.useCallback((isin: string) => list.some((e) => e.isin === isin), [list]);

  const syncMutation = useMutation({
    mutationFn: async (entry: Omit<WatchlistEntry, 'addedAt'>) => {
      const serverList = qc.getQueryData<WatchlistEntry[]>(queryKeys.mf.watchlist()) ?? [];
      if (serverList.some((e) => e.isin === entry.isin)) {
        await api.del<void>(`/mf/watchlist/${entry.isin}`);
      } else {
        await api.put<void>(`/mf/watchlist/${entry.isin}`);
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.mf.watchlist() });
    },
  });

  const toggle = React.useCallback(
    (entry: Omit<WatchlistEntry, 'addedAt'>) => {
      if (!user) {
        const cur = read();
        write(
          cur.some((e) => e.isin === entry.isin)
            ? cur.filter((e) => e.isin !== entry.isin)
            : [...cur, { ...entry, addedAt: new Date().toISOString() }],
        );
        return;
      }
      syncMutation.mutate(entry);
    },
    [user, syncMutation],
  );

  return { list, has, toggle };
}
