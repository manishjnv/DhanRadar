import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWatchlist } from '../watchlist';

const ENTRY = { isin: 'INF174K01KH7', name: 'Kotak Banking and PSU Debt', category: 'Debt' };

describe('useWatchlist', () => {
  beforeEach(() => window.localStorage.clear());

  it('toggle adds then removes, and has() tracks it', () => {
    const { result } = renderHook(() => useWatchlist());
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
    const { result } = renderHook(() => useWatchlist());
    expect(result.current.list).toEqual([]);
    act(() => result.current.toggle(ENTRY));
    expect(result.current.has(ENTRY.isin)).toBe(true);
  });
});
