import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as React from 'react';
import { useWatchlist } from '../useWatchlist';

// Anonymous mode — the localStorage path. Server mode is exercised by the
// backend unit tests + the shared facade shape.
vi.mock('@/features/auth/api', () => ({
  useMe: () => ({ data: undefined }),
}));

const ENTRY = { isin: 'INF174K01KH7', name: 'Kotak Banking and PSU Debt', category: 'Debt' };

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

describe('useWatchlist', () => {
  beforeEach(() => window.localStorage.clear());

  it('toggle adds then removes, and has() tracks it', () => {
    const { result } = renderHook(() => useWatchlist(), { wrapper: createWrapper() });
    expect(result.current.has(ENTRY.isin)).toBe(false);

    act(() => result.current.toggle(ENTRY));
    expect(result.current.has(ENTRY.isin)).toBe(true);
    expect(result.current.list[0]).toMatchObject(ENTRY);

    act(() => result.current.toggle(ENTRY));
    expect(result.current.has(ENTRY.isin)).toBe(false);
    expect(result.current.list).toHaveLength(0);
  });

  it('survives corrupt storage', () => {
    window.localStorage.setItem('dr.watchlist.v1', '{not json');
    const { result } = renderHook(() => useWatchlist(), { wrapper: createWrapper() });
    expect(result.current.list).toEqual([]);
    act(() => result.current.toggle(ENTRY));
    expect(result.current.has(ENTRY.isin)).toBe(true);
  });
});
